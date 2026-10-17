"""Windows local launcher: owned processes only; no database migrations or seeding."""
import argparse
import ctypes
from ctypes import wintypes
import json
import msvcrt
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from contextlib import contextmanager

ROOT=Path(__file__).resolve().parents[1]
BACKEND=ROOT/'backend'
FRONTEND=ROOT/'frontend'
LOGS=BACKEND/'logs'
CONTROL=LOGS/'local-runner-control'
STATE=LOGS/'local-project-state.json'
URL='http://127.0.0.1:5173/#/'
LOG_NAMES={'backend':'local-backend.log','frontend':'local-frontend.log'}
PORTS={'backend':8000,'frontend':5173}


def process_info(pid):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    native=ctypes.WinDLL('ntdll')
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    kernel.GetProcessTimes.argtypes=[wintypes.HANDLE]+[ctypes.POINTER(wintypes.FILETIME)]*4
    native.NtQueryInformationProcess.argtypes=[wintypes.HANDLE,wintypes.ULONG,ctypes.c_void_p,wintypes.ULONG,ctypes.POINTER(wintypes.ULONG)]
    native.NtQueryInformationProcess.restype=wintypes.LONG
    handle=kernel.OpenProcess(0x1000,False,int(pid))
    if not handle:return None
    try:
        stamps=[wintypes.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle,*[ctypes.byref(v) for v in stamps]):return None
        created=(stamps[0].dwHighDateTime<<32)|stamps[0].dwLowDateTime
        size=wintypes.ULONG()
        native.NtQueryInformationProcess(handle,60,None,0,ctypes.byref(size))
        if not 0<size.value<1024*1024:return None
        buf=ctypes.create_string_buffer(size.value)
        if native.NtQueryInformationProcess(handle,60,buf,len(buf),ctypes.byref(size))!=0:return None
        class UnicodeString(ctypes.Structure):
            _fields_=[('length',wintypes.USHORT),('maximum',wintypes.USHORT),('buffer',ctypes.c_void_p)]
        value=UnicodeString.from_buffer(buf)
        command=ctypes.wstring_at(value.buffer,value.length//2)
        return {'created':created,'command':command}
    finally:
        kernel.CloseHandle(handle)


def stop_file(name,token):
    if name not in PORTS or not re.fullmatch('[a-f0-9]{32}',str(token)):raise RuntimeError('Invalid service identity')
    return CONTROL/(name+'-'+token+'.stop')


def owned(name,entry):
    if not isinstance(entry,dict):return False
    try:
        stop_file(name,entry['token'])
        info=process_info(entry['pid'])
        script=ROOT/'tools'/('local_project_runner.py' if name=='backend' else 'frontend_dev_runner.cjs')
        command=(info or {}).get('command','').replace('\\','/').casefold()
        return bool(info and info['created']==entry['created'] and str(script).replace('\\','/').casefold() in command and entry['token'] in command)
    except (KeyError,TypeError,ValueError,RuntimeError):return False


def read_state():
    if not STATE.exists():return {}
    try:
        state=json.loads(STATE.read_text(encoding='utf-8'))
        return {name:entry for name,entry in state.items() if name in PORTS and owned(name,entry)}
    except (ValueError,AttributeError):raise RuntimeError('运行状态文件损坏，请查看 '+str(STATE))


def save_state(state):
    temp=STATE.with_suffix('.tmp')
    temp.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    temp.replace(STATE)


@contextmanager
def manager_lock():
    LOGS.mkdir(exist_ok=True)
    CONTROL.mkdir(exist_ok=True)
    with (LOGS/'local-project.lock').open('a+b') as lock:
        lock.seek(0,2)
        if lock.tell()==0:lock.write(b'0');lock.flush()
        lock.seek(0)
        try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:raise RuntimeError('项目正在启动或停止，请稍候再试。')
        try:yield
        finally:
            lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)


def port_open(port):
    with socket.socket() as sock:
        sock.settimeout(.3)
        return sock.connect_ex(('127.0.0.1',port))==0


def healthy(url):
    try:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url,timeout=3) as response:return response.status==200
    except Exception:return False


def spawn_service(name):
    from uuid import uuid4
    token=uuid4().hex
    flag=stop_file(name,token)
    if name=='backend':
        command=[sys.executable,str(Path(__file__).resolve()),'backend-worker','--token',token]
    else:
        node=shutil.which('node.exe')
        if not node:raise RuntimeError('未找到Node.js，请安装Node.js并重新打开启动脚本。')
        command=[node,str(ROOT/'tools'/'frontend_dev_runner.cjs'),'--token',token]
    env=os.environ.copy()
    env.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONUNBUFFERED='1',BACKEND_PROXY_TARGET='http://127.0.0.1:8000',VITE_API_BASE_URL='/api/v1')
    with (LOGS/LOG_NAMES[name]).open('a',encoding='utf-8') as output:
        output.write('\n[一键启动] '+time.strftime('%Y-%m-%d %H:%M:%S')+'\n');output.flush()
        child=subprocess.Popen(command,cwd=BACKEND if name=='backend' else FRONTEND,env=env,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.CREATE_NEW_PROCESS_GROUP)
    for _ in range(30):
        info=process_info(child.pid)
        if info:
            entry={'pid':child.pid,'created':info['created'],'token':token}
            if owned(name,entry):return entry
        if child.poll() is not None:break
        time.sleep(.1)
    if child.poll() is None:
        # This is the process just created above, before it can be recorded.
        flag.touch()
        try:child.wait(timeout=5)
        except subprocess.TimeoutExpired:child.terminate()
    raise RuntimeError('无法启动'+name+'，请查看日志：'+str(LOGS/LOG_NAMES[name]))


def stop_service(name,entry):
    if not owned(name,entry):return
    flag=stop_file(name,entry['token']);flag.touch()
    deadline=time.monotonic()+12
    while owned(name,entry) and time.monotonic()<deadline:time.sleep(.2)
    if owned(name,entry):
        # Validate identity again before using the PID, preventing PID reuse mistakes.
        subprocess.run(['taskkill','/PID',str(entry['pid']),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
        time.sleep(.3)
    if owned(name,entry):raise RuntimeError('停止失败，请查看运行日志。')
    flag.unlink(missing_ok=True)


def wait_ready(name,entry):
    url='http://127.0.0.1:'+str(PORTS[name])+('/api/v1/health/ready' if name=='backend' else '/')
    deadline=time.monotonic()+(60 if name=='backend' else 30)
    while time.monotonic()<deadline:
        if not owned(name,entry):break
        if healthy(url):return
        time.sleep(.4)
    raise RuntimeError(('后端或云端数据库尚未就绪' if name=='backend' else '前端启动未完成')+'，请查看 '+str(LOGS/LOG_NAMES[name]))


def start(no_browser=False):
    if not (BACKEND/'.env').is_file():raise RuntimeError('缺少 backend/.env，请先填写项目配置。')
    if not (FRONTEND/'node_modules'/'vite'/'dist'/'node'/'index.js').is_file():raise RuntimeError('缺少前端依赖，请在frontend目录运行npm ci。')
    if not shutil.which('node.exe'):raise RuntimeError('未找到Node.js，请先安装Node.js。')
    with manager_lock():
        state=read_state();started=[]
        try:
            for name in ('backend','frontend'):
                print(('正在检查后端及数据库…' if name=='backend' else '正在启动前端…'),flush=True)
                if name not in state:
                    if port_open(PORTS[name]):raise RuntimeError(str(PORTS[name])+'端口被其他运行实例占用，请先停止该实例。')
                    state[name]=spawn_service(name);save_state(state);started.append(name)
                else:print('  '+name+'已运行，直接复用。',flush=True)
                wait_ready(name,state[name])
            if not healthy('http://127.0.0.1:5173/api/v1/health/ready'):raise RuntimeError('前端代理未连接后端，请查看前端日志。')
        except Exception:
            for name in reversed(started):
                stop_service(name,state.pop(name))
            save_state(state)
            raise
    print('\n项目已就绪：'+URL,flush=True)
    print('关闭本窗口后服务继续运行；结束使用时双击“一键停止.cmd”。',flush=True)
    print('日志目录：'+str(LOGS),flush=True)
    if not no_browser:
        if not webbrowser.open(URL,new=2):print('浏览器未自动打开，请复制上面的网址。',flush=True)


def stop():
    with manager_lock():
        state=read_state()
        for name in ('frontend','backend'):
            if name in state:
                print('正在停止'+name+'…',flush=True)
                stop_service(name,state[name]);state.pop(name);save_state(state)
        save_state(state)
    print('项目已停止，5173和8000端口已释放。' if not any(port_open(p) for p in PORTS.values()) else '本脚本启动的服务已停止；仍有其他程序使用项目端口。',flush=True)


def backend_worker(token):
    flag=stop_file('backend',token)
    os.chdir(BACKEND);sys.path.insert(0,str(BACKEND))
    import uvicorn
    server=uvicorn.Server(uvicorn.Config('app.main:app',host='127.0.0.1',port=8000))
    def monitor():
        while not server.should_exit:
            if flag.exists():server.should_exit=True;return
            time.sleep(.25)
    threading.Thread(target=monitor,daemon=True).start()
    server.run()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['start','stop','status','backend-worker'])
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--token')
    args=parser.parse_args()
    if args.action=='backend-worker':backend_worker(args.token);return
    if args.action=='start':start(args.no_browser)
    elif args.action=='stop':stop()
    else:print(json.dumps({name:{'pid':entry['pid'],'port':PORTS[name]} for name,entry in read_state().items()},ensure_ascii=False))


if __name__=='__main__':
    try:main()
    except Exception as error:
        print('\n操作未完成：'+str(error),file=sys.stderr,flush=True)
        raise SystemExit(1)

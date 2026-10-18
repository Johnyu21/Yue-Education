"""Prepare a Windows checkout, then delegate to the local service runner.

Only dependencies and ignored local configuration are created. Database migrations
and account creation remain explicit operations, never part of daily startup.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'backend'
FRONTEND = ROOT / 'frontend'
VENV = BACKEND / '.venv'
PYTHON = VENV / 'Scripts' / 'python.exe'
LOGS = BACKEND / 'logs'
STAMP = LOGS / 'local-setup.json'
REQUIRED = (
    'tools/local_project_runner.py', 'tools/frontend_dev_runner.cjs',
    'backend/.env.example', 'backend/requirements.lock.txt',
    'frontend/package.json', 'frontend/package-lock.json', 'frontend/vite.config.ts',
)


@contextmanager
def setup_lock():
    import msvcrt
    LOGS.mkdir(parents=True, exist_ok=True)
    with (LOGS / 'local-setup.lock').open('a+b') as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise RuntimeError('另一个窗口正在准备环境，请等待完成后再试。')
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def run(command):
    return subprocess.run([str(v) for v in command], cwd=ROOT, check=True)


def digest(*paths):
    result = hashlib.sha256()
    for path in paths:
        result.update(Path(path).read_bytes())
        result.update(b'\0')
    return result.hexdigest()


def check_files():
    missing = [name for name in REQUIRED if not (ROOT / name).is_file()]
    if missing:
        raise RuntimeError('仓库文件不完整，请重新拉取：' + ', '.join(missing))


def python_ready():
    if not PYTHON.is_file():
        return False
    probe = ('import sys,pathlib; '
             'assert (3,12) <= sys.version_info[:2] < (3,14); '
             'assert pathlib.Path(sys.prefix).resolve() == pathlib.Path(sys.argv[1]).resolve()')
    try:
        result = subprocess.run([str(PYTHON), '-c', probe, str(VENV)],
                                capture_output=True, timeout=15)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def read_stamp():
    try:
        value = json.loads(STAMP.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def write_stamp(value):
    LOGS.mkdir(parents=True, exist_ok=True)
    temporary = STAMP.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(STAMP)


def ensure_env():
    target = BACKEND / '.env'
    if target.exists():
        return False
    source = (BACKEND / '.env.example').read_text(encoding='utf-8-sig')
    source = source.replace('JWT_SECRET=replace-with-random-secret-at-least-32-characters',
                            'JWT_SECRET=' + secrets.token_urlsafe(48))
    # Exclusive creation prevents replacing a teammate's existing configuration.
    with target.open('x', encoding='utf-8', newline='\n') as output:
        output.write(source)
    print('已生成 backend/.env（不会提交到 Git）；请填写数据库连接信息。', flush=True)
    return True


def config_problems():
    target = BACKEND / '.env'
    if not target.is_file():
        return ['缺少 backend/.env']
    values = {}
    for line in target.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    problems = []
    for key in ('POSTGRES_HOST', 'POSTGRES_PORT', 'POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD', 'JWT_SECRET'):
        value = os.environ.get(key, values.get(key, ''))
        if not value or value.lower().startswith(('replace-', 'your_', '填入', '<')):
            problems.append('请填写 ' + key)
    return problems


def node_commands():
    node = shutil.which('node.exe') or shutil.which('node')
    npm = shutil.which('npm.cmd') or shutil.which('npm')
    if not node or not npm:
        raise RuntimeError('未找到 Node.js/npm。请安装 Node.js 22 或 24 LTS，然后重新打开脚本。')
    result = subprocess.run([node, '--version'], capture_output=True, text=True, check=True)
    major = int(result.stdout.strip().lstrip('v').split('.')[0])
    if major < 20:
        raise RuntimeError('Node.js 版本过旧，需要 20 及以上；建议使用 22 或 24 LTS。')
    return node, npm


def dependencies_ready():
    if not python_ready():
        return False
    probe = ('import uvicorn,fastapi,sqlalchemy,psycopg,pydantic_settings,bcrypt,jwt,'
             'multipart,httpx,pypdf,docx,reportlab,openpyxl,tzdata')
    result = subprocess.run([str(PYTHON), '-c', probe], capture_output=True, timeout=30)
    return result.returncode == 0


def prepare(repair=False):
    check_files()
    node, npm = node_commands()
    if not (3, 12) <= sys.version_info[:2] < (3, 14):
        raise RuntimeError('请安装 Python 3.12 或 3.13，并重新打开脚本。')
    ensure_env()
    if not python_ready():
        if VENV.exists():
            raise RuntimeError('backend/.venv 无法使用或来自旧位置。请将该目录移到项目外备份后重试；不要复制别人的虚拟环境。')
        print('首次运行：正在创建本机 Python 虚拟环境…', flush=True)
        run([sys.executable, '-m', 'venv', VENV])
    stamp = read_stamp()
    backend_hash = digest(BACKEND / 'requirements.lock.txt')
    frontend_hash = digest(FRONTEND / 'package.json', FRONTEND / 'package-lock.json')
    if repair or stamp.get('backend') != backend_hash or not dependencies_ready():
        print('正在安装后端锁定依赖（首次可能需要几分钟）…', flush=True)
        run([PYTHON, '-m', 'pip', 'install', '--disable-pip-version-check', '-r', BACKEND / 'requirements.lock.txt'])
        run([PYTHON, '-m', 'pip', 'check'])
        if not dependencies_ready():
            raise RuntimeError('后端依赖校验失败，请使用“一键准备环境.cmd --repair”重装。')
        stamp['backend'] = backend_hash
        write_stamp(stamp)
    vite = FRONTEND / 'node_modules/vite/dist/node/index.js'
    if repair or stamp.get('frontend') != frontend_hash or not vite.is_file():
        print('正在安装前端锁定依赖…', flush=True)
        subprocess.run([npm, 'ci', '--no-audit', '--no-fund'], cwd=FRONTEND, check=True)
        stamp['frontend'] = frontend_hash
        write_stamp(stamp)
    print('本机依赖准备完成。', flush=True)
    problems = config_problems()
    if problems:
        print('下一步：编辑 ' + str(BACKEND / '.env'), flush=True)
        raise RuntimeError('；'.join(problems) + '。配置好后再次双击“一键启动.cmd”。')


def check():
    check_files()
    problems = []
    if not python_ready():
        problems.append('缺少可用的 backend/.venv')
    elif not dependencies_ready():
        problems.append('后端依赖不完整')
    try:
        node_commands()
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        problems.append(str(error))
    if not (FRONTEND / 'node_modules/vite/dist/node/index.js').is_file():
        problems.append('缺少前端 node_modules')
    problems.extend(config_problems())
    if problems:
        raise RuntimeError('；'.join(problems))
    print('文件、依赖和配置检查通过（数据库连通性将在启动时验证）。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'stop', 'status', 'prepare', 'check'])
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--repair', action='store_true')
    args = parser.parse_args()
    if args.action == 'check':
        check()
        return
    if args.action in ('start', 'prepare'):
        with setup_lock():
            prepare(args.repair)
    if args.action == 'prepare':
        return
    worker = PYTHON if python_ready() else Path(sys.executable)
    command = [worker, ROOT / 'tools/local_project_runner.py', args.action]
    if args.no_browser:
        command.append('--no-browser')
    run(command)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('操作已取消；再次运行可继续准备环境。', file=sys.stderr)
        raise SystemExit(130)
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            message = '子命令失败，请查看上面的错误；检查网络和依赖源后重试。退出码：' + str(error.returncode)
        else:
            message = str(error)
        print('\n操作未完成：' + message, file=sys.stderr, flush=True)
        raise SystemExit(1)

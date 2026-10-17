// Runs against synthetic fixtures in a fresh guarded *_test database schema only.
const cp=require('node:child_process'),net=require('node:net'),path=require('node:path'),fs=require('node:fs')
const {once}=require('node:events')
const {setTimeout:sleep}=require('node:timers/promises')
const root=path.resolve(__dirname,'..'),python=process.env.UI_QA_PYTHON||path.resolve(root,'../backend/.venv/Scripts/python.exe')
let backend,vite,backendClosed,backendLog=''
function freePort(){return new Promise((resolve,reject)=>{const s=net.createServer();s.on('error',reject);s.listen(0,'127.0.0.1',()=>{const port=s.address().port;s.close(()=>resolve(port))})})}
async function until(check,timeout=60000){const deadline=Date.now()+timeout;while(Date.now()<deadline){if(await check())return;await sleep(100)}throw new Error('Isolated QA startup timed out')}
(async()=>{
 if(!fs.existsSync(python))throw new Error('Set UI_QA_PYTHON to the backend Python executable')
 const backendPort=await freePort(),frontendPort=await freePort()
 backend=cp.spawn(python,['scripts/backend-qa-server.py'],{cwd:root,env:{...process.env,UI_QA_BACKEND_PORT:String(backendPort)},stdio:['pipe','pipe','pipe']})
 backendClosed=once(backend,'exit')
 backend.stdout.on('data',d=>backendLog+=d);backend.stderr.on('data',d=>backendLog+=d)
 await until(()=>{if(backend.exitCode!==null)throw new Error('QA backend failed: '+backendLog.slice(-2000));return backendLog.includes('UI_QA_READY')})
 vite=cp.spawn(process.execPath,[path.join(path.dirname(require.resolve('vite/package.json')),'bin/vite.js'),'--mode','qa','--host','127.0.0.1','--port',String(frontendPort),'--strictPort'],{cwd:root,env:{...process.env,BACKEND_PROXY_TARGET:'http://127.0.0.1:'+backendPort},stdio:['ignore','ignore','pipe']})
 vite.stderr.on('data',d=>process.stderr.write(d))
 const url='http://127.0.0.1:'+frontendPort
 await until(async()=>{if(vite.exitCode!==null)throw new Error('QA frontend failed');try{return (await fetch(url+'/api/v1/__ui_qa__/identity')).ok}catch{return false}},20000)
 const browser=cp.spawn(process.execPath,['scripts/browser-smoke.cjs'],{cwd:root,env:{...process.env,UI_QA_URL:url},stdio:'inherit'})
 const [code]=await once(browser,'exit');if(code!==0)throw new Error('Browser checks failed')
})().catch(e=>{console.error(e.message);process.exitCode=1}).finally(async()=>{
 if(vite&&vite.exitCode===null)vite.kill()
 if(backend&&backend.exitCode===null){backend.stdin.write('stop\n');const [code]=await backendClosed;if(code!==0){console.error('QA schema cleanup failed');process.exitCode=1}else console.log('QA schema and temporary files removed')}
})

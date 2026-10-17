// Local Vite worker; shutdown is controlled by the project launcher.
const fs=require('node:fs'),path=require('node:path'),{pathToFileURL}=require('node:url')
const root=path.resolve(__dirname,'..'),token=process.argv[process.argv.indexOf('--token')+1]
if(!/^[a-f0-9]{32}$/.test(token||''))throw new Error('Invalid service identity')
const flag=path.join(root,'backend/logs/local-runner-control','frontend-'+token+'.stop')
let server,timer,closing=false
async function close(){if(closing)return;closing=true;clearInterval(timer);try{await server?.close()}finally{process.exit(0)}}
;(async()=>{
 process.chdir(path.join(root,'frontend'))
 const {createServer}=await import(pathToFileURL(path.join(root,'frontend/node_modules/vite/dist/node/index.js')).href)
 server=await createServer({root:path.join(root,'frontend'),configFile:path.join(root,'frontend/vite.config.ts'),mode:'development',server:{host:'127.0.0.1',port:5173,strictPort:true}})
 await server.listen();server.printUrls()
 timer=setInterval(()=>{if(fs.existsSync(flag))void close()},250)
 process.once('SIGINT',close);process.once('SIGTERM',close)
 if(fs.existsSync(flag))await close()
})().catch(error=>{console.error(error.message);process.exit(1)})

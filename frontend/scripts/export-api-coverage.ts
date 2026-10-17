import {writeFileSync} from 'node:fs'
import {resolve} from 'node:path'
import {apiCoverage} from '../src/api/coverage'
const result=apiCoverage()
writeFileSync(resolve('../docs/前端接口覆盖清单.json'),JSON.stringify({...result,scope:'界面/调用映射覆盖；不等同于每项接口均通过真实云端联调'},null,2)+'\n')
const lines=['# 前端接口对接清单','','生成自正式后端 OpenAPI 和前端业务入口映射。覆盖登记不代表真实云端全量联调通过。','', '| 方法与路径 | 前端功能 | 备注 |','|---|---|---|',...result.entries.map(e=>'| '+e.endpoint+' | '+(e.feature||'未接入')+' | '+(e.alias?'与主接口共享同一业务界面':'')+' |')]
writeFileSync(resolve('../docs/前端接口对接清单.md'),lines.join('\n')+'\n')
console.log(JSON.stringify({total:result.total,connected:result.connected,missing:result.missing,obsolete:result.obsolete},null,2))
if(result.missing.length||result.obsolete.length)process.exitCode=1

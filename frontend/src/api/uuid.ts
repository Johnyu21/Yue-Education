// crypto.randomUUID 只在 HTTPS / localhost 安全上下文可用；
// 内网 HTTP（如 http://192.168.x.x）访问时该 API 不存在，需降级兜底。
export function uuid():string{
  const c=globalThis.crypto
  if(c&&typeof c.randomUUID==='function')return c.randomUUID()
  if(c&&typeof c.getRandomValues==='function'){
    const b=c.getRandomValues(new Uint8Array(16))
    b[6]=(b[6]&0x0f)|0x40
    b[8]=(b[8]&0x3f)|0x80
    const h=[...b].map(x=>x.toString(16).padStart(2,'0')).join('')
    return h.slice(0,8)+'-'+h.slice(8,12)+'-'+h.slice(12,16)+'-'+h.slice(16,20)+'-'+h.slice(20)
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g,ch=>{const r=Math.random()*16|0;return (ch==='x'?r:(r&0x3|0x8)).toString(16)})
}

import {webcrypto} from 'node:crypto'
Object.defineProperty(globalThis,'crypto',{value:webcrypto})
Object.defineProperty(HTMLElement.prototype,'scrollTo',{value:()=>{}})
Object.defineProperty(window,'scrollTo',{value:()=>{}})

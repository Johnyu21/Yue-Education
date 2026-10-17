import { createApp } from 'vue'
import { createRouter,createWebHashHistory } from 'vue-router'
import App from './App.vue'
import './style.css'
import './business.css'
const Empty={template:'<div />'}
const router=createRouter({history:createWebHashHistory(),routes:[{path:'/:pathMatch(.*)*',component:Empty}]})
createApp(App).use(router).mount('#app')

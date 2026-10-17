<script setup lang="ts">
import {computed,onMounted,onBeforeUnmount,ref,watch} from 'vue'
import {useRoute} from 'vue-router'
import {GraduationCap,ArrowUpRight,Bell,ChevronDown,UserRound,KeyRound,LogOut,Settings,Users,X} from 'lucide-vue-next'
const props=defineProps<{user:any;notifications:any}>()
const emit=defineEmits(['navigate','logout','profile','password','notification','refreshNotifications'])
const route=useRoute(),root=ref<HTMLElement|null>(null),menu=ref<'account'|'notifications'|null>(null)
const recent=computed(()=>(props.notifications?.items||[]).slice(0,6))
function close(){menu.value=null}
function toggle(next:'account'|'notifications'){menu.value=menu.value===next?null:next;if(menu.value==='notifications'&&!props.user.mustChangePassword)emit('refreshNotifications')}
function action(name:string,payload?:any){close();emit(name as any,payload)}
function outside(e:PointerEvent){if(root.value&&!root.value.contains(e.target as Node))close()}
function time(value:string){return value?new Date(value).toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}):''}
watch(()=>route.fullPath,close)
onMounted(()=>document.addEventListener('pointerdown',outside))
onBeforeUnmount(()=>document.removeEventListener('pointerdown',outside))
</script>
<template><header ref="root" class="workspace-header" @keydown.esc.stop="close"><a class="brand" href="#/"><span class="brand-mark"><GraduationCap :size="27"/></span><span><strong>粤教服务</strong><small>教育服务管理平台</small></span></a><div class="workspace-toplinks"><a href="#/">门户首页 <ArrowUpRight :size="13"/></a><span>工作空间</span></div><div class="account header-tools">
<div v-if="!user.mustChangePassword" class="header-popover-anchor"><button class="icon-btn notification-trigger" aria-label="通知预览" aria-haspopup="dialog" :aria-expanded="menu==='notifications'" aria-controls="notification-popover" @click="toggle('notifications')"><Bell :size="21"/><span v-if="notifications?.unread" class="notification-count">{{notifications.unread>99?'99+':notifications.unread}}</span></button>
<section v-if="menu==='notifications'" id="notification-popover" class="header-popover notification-popover" role="dialog" aria-label="通知预览"><div class="popover-heading"><div><h3>通知消息</h3><small>{{notifications?.unread||0}} 条未读</small></div><button class="icon-btn" aria-label="关闭通知预览" @click="close"><X :size="17"/></button></div><div class="notification-preview-list"><button v-for="n in recent" :key="n.id" class="notification-preview-item" :class="{unread:!n.read}" @click="action('notification',n)"><span class="notice-dot"></span><span><strong>{{n.title}}</strong><small>{{n.content}}</small><time>{{time(n.createTime)}}</time></span></button><p v-if="!recent.length" class="popover-empty">暂无通知，新的服务消息会在这里提醒您。</p></div><button class="popover-footer" @click="action('navigate','/app/notifications')">查看全部通知 <ArrowUpRight :size="14"/></button></section></div>
<div class="header-popover-anchor"><button class="account-trigger" aria-label="个人设置" aria-haspopup="menu" :aria-expanded="menu==='account'" aria-controls="account-menu" @click="toggle('account')"><span class="avatar">{{(user.real_name||user.realName||'我').slice(-1)}}</span><span class="account-caption"><strong>{{user.real_name}}</strong><small>{{user.role_name}} · {{user.dept_name}}</small></span><ChevronDown :size="16" :class="{rotated:menu==='account'}"/></button>
<div v-if="menu==='account'" id="account-menu" class="header-popover account-menu" role="menu" aria-label="个人设置菜单"><div class="account-menu-heading"><strong>{{user.realName}}</strong><small>{{user.role_name}}</small></div><button role="menuitem" :disabled="user.mustChangePassword" @click="action('profile')"><UserRound :size="17"/>个人资料</button><button role="menuitem" @click="action('password')"><KeyRound :size="17"/>修改密码</button><button v-if="!user.mustChangePassword" role="menuitem" @click="action('navigate','/app/settings')"><Settings :size="17"/>账号与附件</button><button v-if="user.isAdmin&&!user.mustChangePassword" role="menuitem" @click="action('navigate','/app/accounts')"><Users :size="17"/>账号管理</button><button role="menuitem" class="logout-menu-item" aria-label="退出登录" @click="action('logout')"><LogOut :size="17"/>退出登录</button></div></div>
</div></header></template>

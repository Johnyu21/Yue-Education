<script setup lang="ts">
import {computed, nextTick, onBeforeUnmount, onMounted, ref, useId} from 'vue'
import {ChevronDown, Search, X} from 'lucide-vue-next'

const props = defineProps<{
  modelValue: string[]
  students: {id: string; name: string; class_name?: string}[]
}>()
const emit = defineEmits<{ 'update:modelValue': [value: string[]] }>()
const id = useId()
const root = ref<HTMLElement | null>(null)
const trigger = ref<HTMLButtonElement | null>(null)
const searchInput = ref<HTMLInputElement | null>(null)
const open = ref(false)
const query = ref('')
const selected = computed(() => props.modelValue.map(id => ({
  id,
  name: props.students.find(student => student.id === id)?.name || '学生信息暂不可用'
})))
const filtered = computed(() => {
  const keyword = query.value.trim().toLocaleLowerCase()
  return props.students.filter(student =>
    `${student.name} ${student.class_name || ''}`.toLocaleLowerCase().includes(keyword))
})

function select(id: string, checked: boolean) {
  emit('update:modelValue', checked
    ? [...new Set([...props.modelValue, id])]
    : props.modelValue.filter(value => value !== id))
}
async function toggle() {
  open.value = !open.value
  query.value = ''
  if (open.value) {
    await nextTick()
    searchInput.value?.focus()
  }
}
function closeWithKeyboard() {
  if (!open.value) return
  open.value = false
  trigger.value?.focus()
}
function outside(event: PointerEvent) {
  if (event.target instanceof Node && !root.value?.contains(event.target)) open.value = false
}
onMounted(() => document.addEventListener('pointerdown', outside))
onBeforeUnmount(() => document.removeEventListener('pointerdown', outside))
</script>

<template>
  <div ref="root" class="student-picker" @keydown.esc.stop.prevent="closeWithKeyboard">
    <span :id="id + '-label'" class="student-picker-label">关联学生 <span>（选填）</span></span>
    <div v-if="selected.length" class="student-picker-tags" aria-label="已关联学生">
      <span v-for="student in selected" :key="student.id" class="student-picker-tag">
        <span>{{student.name}}</span>
        <button type="button" :aria-label="'移除关联学生：' + student.name" @click="select(student.id, false)"><X :size="12"/></button>
      </span>
    </div>
    <button :id="id + '-trigger'" ref="trigger" type="button" class="student-picker-trigger"
      :aria-labelledby="id + '-label ' + id + '-value'" :aria-expanded="open" :aria-controls="id + '-options'" @click="toggle">
      <span :id="id + '-value'">{{selected.length ? '已选 ' + selected.length + ' 人 · 修改' : '不关联学生 · 点击选择'}}</span>
      <ChevronDown :size="15" :class="{expanded: open}"/>
    </button>
    <div v-if="open" :id="id + '-options'" class="student-picker-popover" role="group" aria-label="选择关联学生">
      <div class="student-picker-search"><Search :size="15"/><input ref="searchInput" v-model="query" type="search" aria-label="搜索关联学生" placeholder="搜索姓名或班级"></div>
      <p class="student-picker-hint">仅选择本项工作涉及的学生，可多选；普通事务可不选。</p>
      <div class="student-picker-options">
        <label v-for="student in filtered" :key="student.id" class="student-picker-option">
          <input type="checkbox" :checked="modelValue.includes(student.id)" @change="select(student.id, ($event.target as HTMLInputElement).checked)">
          <span><strong>{{student.name}}</strong><small v-if="student.class_name">{{student.class_name}}</small></span>
        </label>
        <p v-if="!filtered.length" class="student-picker-empty">{{query.trim() ? '没有找到匹配的学生' : '暂无可关联的学生，可保持不关联'}}</p>
      </div>
      <div class="student-picker-footer"><button v-if="selected.length" type="button" @click="emit('update:modelValue', [])">清空选择</button><span v-else>当前不关联学生</span><button type="button" @click="open = false">完成</button></div>
    </div>
  </div>
</template>

<style scoped>
.student-picker{position:relative;flex:0 0 230px;min-width:0;font-size:12px}
.student-picker-label{display:block;margin-bottom:6px;color:#667580;font-size:11px}
.student-picker-label>span{color:#929da6}
.student-picker-trigger{display:flex;width:100%;align-items:center;justify-content:space-between;gap:8px;padding:10px 11px;border:1px solid var(--border);border-radius:6px;background:#fff;color:#64737f;text-align:left;font-size:12px;min-height:40px}
.student-picker-trigger:hover{border-color:#c69398}
.student-picker-trigger:focus-visible,.student-picker-tag button:focus-visible{outline:2px solid var(--red);outline-offset:2px}
.student-picker-trigger svg{flex-shrink:0;transition:transform .15s}
.student-picker-trigger svg.expanded{transform:rotate(180deg)}
.student-picker-tags{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:6px}
.student-picker-tag{display:inline-flex;align-items:center;gap:5px;max-width:100%;padding:4px 7px;background:#fbefef;border:1px solid #f1d9dc;border-radius:5px;color:#9b3c48;font-size:11px}
.student-picker-tag>span{overflow-wrap:anywhere}
.student-picker-tag button{display:inline-flex;align-items:center;justify-content:center;border:0;background:none;color:inherit;padding:3px;flex-shrink:0;border-radius:3px}
.student-picker-popover{position:absolute;top:100%;right:0;z-index:30;width:320px;max-width:calc(100vw - 64px);margin-top:6px;border:1px solid var(--border);border-radius:8px;background:white;box-shadow:0 8px 28px #27333f1c;padding:12px}
.student-picker-search{display:flex;align-items:center;gap:7px;border:1px solid var(--border);border-radius:5px;padding:0 9px;color:#929da6}
.student-picker-search input{width:100%;min-width:0;border:0;background:transparent;padding:9px 0;font-size:12px;outline:none;box-shadow:none}
.student-picker-hint{margin:9px 0;color:#89959f;font-size:11px;line-height:1.7}
.student-picker-options{max-height:210px;overflow-y:auto;overscroll-behavior:contain}
.student-picker-option{display:flex;flex-direction:row;align-items:center;gap:10px;padding:9px 7px;border-radius:4px;cursor:pointer}
.student-picker-option:hover{background:#faf4f4}
.student-picker-option input{width:16px;height:16px;flex-shrink:0;margin:0;accent-color:var(--red)}
.student-picker-option strong{display:block;font-size:12px;font-weight:500;color:#4f606c}
.student-picker-option small{display:block;margin-top:3px;font-size:10px;color:#8c98a2}
.student-picker-empty{padding:15px 5px;font-size:12px;color:#89959f;line-height:1.8}
.student-picker-footer{display:flex;justify-content:space-between;align-items:center;border-top:1px solid var(--border);padding-top:10px;margin-top:9px;font-size:11px;color:#89959f}
.student-picker-footer button{border:0;background:none;padding:4px;color:#a7424d;font-size:12px}
@media(max-width:760px){.student-picker{flex:1 0 100%;order:3}.student-picker-popover{left:0;right:auto;width:100%;max-width:100%;box-sizing:border-box}}
</style>

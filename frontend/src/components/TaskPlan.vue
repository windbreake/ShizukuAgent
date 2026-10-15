<template>
  <section v-if="items.length" class="task-plan" aria-label="任务计划">
    <button class="task-plan-heading" :aria-expanded="expanded" @click="expanded=!expanded"><span>已完成 {{completed}} 个任务（共 {{items.length}} 个）</span><span v-if="!expanded" class="current-task">{{currentTask}}</span><UiIcon name="chevron" :class="{expanded}"/></button>
    <div v-if="expanded" class="task-plan-list"><div v-for="(item,index) in items" :key="index" class="plan-item" :class="item.status"><span class="task-status"><UiIcon v-if="item.status==='completed'" name="check" :size="12"/><span v-else-if="item.status==='in_progress'" class="task-dot"/><span v-else-if="item.status==='cancelled'">−</span></span><span>{{item.content}}</span><small v-if="item.status==='in_progress'">{{running?'进行中':'未完成'}}</small></div></div>
    <p v-if="error" class="hint">{{error}}</p>
  </section>
</template>
<script setup lang="ts">
import {computed,onUnmounted,ref,watch} from 'vue';
import {request} from '../store/app';
const props=defineProps<{threadId:string;persona:string;active:boolean}>();
type Task={content:string;status:'pending'|'in_progress'|'completed'|'cancelled';priority:string};
const items=ref<Task[]>([]),running=ref(false),expanded=ref(true),error=ref('');
const completed=computed(()=>items.value.filter(t=>t.status==='completed').length),currentTask=computed(()=>items.value.find(t=>t.status==='in_progress')?.content||'');
let timer:ReturnType<typeof setInterval>|undefined;let generation=0;let inFlight=false;
async function poll(){if(!props.threadId||inFlight)return;inFlight=true;const version=generation,thread=props.threadId,persona=props.persona;try{const data=await request<{items:Task[];running:boolean}>('/api/task-plan?'+new URLSearchParams({thread_id:thread,persona}));if(version!==generation)return;items.value=data.items||[];running.value=Boolean(data.running);error.value='';}catch(e){if(version===generation&&items.value.length)error.value='任务计划暂时无法刷新';}finally{inFlight=false;}}
watch(()=>[props.threadId,props.persona],()=>{generation++;items.value=[];running.value=false;expanded.value=true;void poll();});
watch(()=>props.active,active=>{clearInterval(timer);void poll();if(active){expanded.value=true;timer=setInterval(poll,500);}},{immediate:true});
onUnmounted(()=>{generation++;clearInterval(timer);});
</script>
<style scoped>
.task-plan{background:var(--bg-raised);border:1px solid var(--border);border-radius:12px;margin-bottom:8px;overflow:hidden;}.task-plan-heading{display:flex;align-items:center;gap:14px;width:100%;padding:13px 16px;font-size:12px;color:var(--muted);text-align:left;}.task-plan-heading>.ui-icon{margin-left:auto;transition:transform 180ms;}.task-plan-heading>.expanded{transform:rotate(180deg);}.current-task{overflow:hidden;white-space:nowrap;text-overflow:ellipsis;flex:1;}.task-plan-list{padding:0 16px 12px;display:grid;gap:9px;max-height:200px;overflow:auto;}.plan-item{display:flex;align-items:baseline;gap:10px;font-size:12px;line-height:1.6;}.plan-item>span:nth-child(2){overflow-wrap:anywhere;}.task-status{display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;border:1px solid var(--border);border-radius:4px;flex:0 0 16px;align-self:flex-start;margin-top:2px;}.task-dot{width:5px;height:5px;border-radius:50%;background:var(--accent);}.in_progress .task-status{background:var(--accent-dim);border-color:var(--accent);}.completed,.cancelled{color:var(--muted);}.completed>span:nth-child(2),.cancelled>span:nth-child(2){text-decoration:line-through;}.completed .task-status{background:var(--surface-2);}.plan-item small{color:var(--muted);font-size:10px;white-space:nowrap;}.hint{padding:0 16px;}
</style>

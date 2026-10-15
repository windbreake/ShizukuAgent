<template><section v-if="items.length" class="approval-bar" aria-live="polite"><header><ShieldAlert :size="19"/><strong>需要权限</strong><span>本轮等待审批</span></header><p>{{items[0].kind==='external_directory'?'访问工作区之外的文件或目录':'执行工具或使用辅助模型'}}</p><pre>{{items[0].detail}}</pre><div v-if="items[0].choices.length" class="approval-choices"><label v-for="choice in items[0].choices" :key="choice.id"><input v-model="selected" type="radio" :value="choice.id"/>{{choice.name}}</label></div><p v-if="error" role="alert">{{error}}</p><footer><button class="btn btn-ghost" :disabled="busy" @click="decide('reject')">拒绝并结束本轮</button><button v-if="!items[0].choices.length" class="btn" :disabled="busy" @click="decide('always')">本会话始终允许</button><button class="btn btn-primary" :disabled="busy || (items[0].choices.length>0&&!selected)" @click="decide('once')">允许一次</button></footer></section></template>
<script setup lang="ts">
import {onMounted,onUnmounted,ref,watch} from 'vue';import {ShieldAlert} from 'lucide-vue-next';import {request} from '../store/app';
import {notify} from '../store/notifications';
const props=defineProps<{threadId:string;persona:string;active:boolean}>();
type Item={id:string;kind:string;detail:string;choices:{id:string;name:string}[]};const items=ref<Item[]>([]),selected=ref(''),error=ref(''),busy=ref(false);let timer:ReturnType<typeof setInterval>;
watch(error,message=>{if(message){notify(message);error.value='';}});
async function poll(){if(!props.active||!props.threadId){items.value=[];return;}try{const data=await request<{items:Item[]}>(`/api/approvals?thread_id=${encodeURIComponent(props.threadId)}&persona=${encodeURIComponent(props.persona)}`);if(items.value[0]?.id!==data.items[0]?.id)selected.value='';items.value=data.items;}catch(e){error.value=e instanceof Error?e.message:'读取审批失败';}}
async function decide(decision:string){busy.value=true;try{await request(`/api/approvals/${items.value[0].id}`,{method:'POST',body:JSON.stringify({thread_id:props.threadId,persona:props.persona,decision,selected:selected.value||null})});items.value=[];error.value='';}catch(e){error.value=e instanceof Error?e.message:'审批失败';}finally{busy.value=false;}}
watch(()=>props.active,poll);onMounted(()=>{timer=setInterval(poll,650);});onUnmounted(()=>clearInterval(timer));
</script>
<style scoped>.approval-bar{border:1px solid var(--border);border-radius:12px;background:var(--surface);padding:16px;margin-bottom:10px;box-shadow:0 3px 12px #0001;max-height:260px;overflow:auto;animation:page-in 180ms ease-out;}header{display:flex;align-items:center;gap:9px;font-size:13px;}header svg{color:var(--warn)}header span{margin-left:auto;color:var(--muted);font-size:11px}p{font-size:12px;color:var(--muted)}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:80px;font-size:11px}footer{display:flex;justify-content:flex-end;gap:8px}.approval-choices{display:grid;gap:8px;font-size:12px}</style>
<style scoped>
.approval-bar{position:absolute;left:0;right:0;bottom:0;z-index:120;margin:0;max-height:min(340px,60dvh);box-sizing:border-box;background:var(--surface);box-shadow:0 8px 32px #0002;}
footer>.btn-primary,footer>.btn-primary:hover,footer>.btn-primary:focus-visible{background:var(--fg);color:var(--bg);border-color:var(--fg);}
footer>.btn-primary:hover:not(:disabled){opacity:.85;}
</style>

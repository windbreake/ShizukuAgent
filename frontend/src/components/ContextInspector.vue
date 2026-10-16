<template>
  <button class="context-trigger" type="button" aria-label="查看上下文" :title="`上下文使用率 ${context.usage_percent||0}%（估算）`" @click="open=true;load()"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8" class="ring-track"/><circle cx="12" cy="12" r="8" class="ring-value" :style="{'stroke-dasharray':`${Math.min(100,context.usage_percent||0)*.503} 50.3`}"/></svg><span>{{context.usage_percent||0}}%</span></button>
  <SettingsDialog :visible="open" title="上下文" @close="open=false">
    <div class="context-actions"><span>模型上下文与原始记录</span><button class="btn" :disabled="active||busy||!threadId" @click="compact">{{busy?'正在压缩…':'压缩上下文'}}</button><button class="btn" :disabled="!data" @click="exportSession">导出会话</button></div>
    <p class="context-note">Token 为本地估算；模型未提供窗口大小时按 32,768 估算。压缩仅改变发送给模型的内容，保留原始消息。</p>
    <dl class="context-stats"><template v-for="[label,value] in stats" :key="label"><div><dt>{{label}}</dt><dd>{{value}}</dd></div></template></dl>
    <h3>上下文细分（估算）</h3><div class="context-bar"><span v-for="(value,key) in data?.parts||{}" :key="key" :class="String(key)" :style="{flex:Number(value)||0}" :title="`${key}: ${value}`"/></div><p class="context-note">用户 · 助手 · 工具 · 系统提示</p>
    <details v-if="context.compaction?.summary" open><summary>压缩摘要 · 已覆盖 {{context.compaction.count}} 条模型消息</summary><pre>{{context.compaction.summary}}</pre></details>
    <div class="context-tabs"><button class="btn" :class="{selected:tab==='request'}" @click="tab='request'">最近模型上下文</button><button class="btn" :class="{selected:tab==='original'}" @click="tab='original'">原始消息</button></div>
    <p class="context-note">{{tab==='request'?'显示最近一次发送前的压缩上下文；人格提示在每次请求中另行强化。':'包含原始消息及工具调用结果，不受压缩影响。'}}</p>
    <div class="context-messages"><details v-for="(message,index) in shownMessages" :key="message.id||index"><summary>{{message.role}} · {{message.id||index+1}} <small>{{estimate(message)}} tokens ≈</small></summary><pre>{{JSON.stringify(message,null,2)}}</pre></details><p v-if="!shownMessages.length" class="context-note">暂无上下文，请先发送消息。</p></div>
    <ToastNotice :message="error"/>
  </SettingsDialog>
</template>
<script setup lang="ts">
import {computed,onUnmounted,ref,watch} from 'vue';
import SettingsDialog from './SettingsDialog.vue';
import {request} from '../store/app';
const props=defineProps<{threadId:string;persona:string;modelId:string;active:boolean}>();
const open=ref(false),busy=ref(false),error=ref(''),tab=ref('request');
const data=ref<any>(null),context=computed(()=>data.value?.context||{});
let generation=0;
async function load(){const version=++generation;if(!props.threadId){data.value=null;return;}try{const result=await request('/api/workbench/context?'+new URLSearchParams({thread_id:props.threadId,persona:props.persona}));if(version===generation)data.value=result;}catch(e){if(version===generation&&open.value)error.value=String(e);}}
watch(()=>[props.threadId,props.persona],()=>{data.value=null;void load();},{immediate:true});
watch(()=>props.active,()=>{void load();});
const timer=setInterval(()=>{if(open.value||props.active)void load();},2500);
onUnmounted(()=>{generation++;clearInterval(timer);});
async function compact(){busy.value=true;error.value='';try{data.value=await request('/api/workbench/context/compact',{method:'POST',body:JSON.stringify({thread_id:props.threadId,persona:props.persona,model_id:props.modelId||undefined})});}catch(e){error.value=String(e);}finally{busy.value=false;}}
function estimate(message:unknown){return Math.ceil(JSON.stringify(message).length/3);}
const shownMessages=computed<any[]>(()=>tab.value==='original'?data.value?.messages||[]:context.value.request_messages||[]);
const stats=computed(()=>[['人格',props.persona],['模型',context.value.model||'尚未调用'],['提供商',context.value.provider||'—'],['消息数',data.value?.message_count||0],['上下文限制',context.value.context_limit?`${context.value.context_limit.toLocaleString()}${context.value.limit_assumed?'（默认估算）':''}`:'—'],['上下文 token（估算）',context.value.estimated_tokens?.toLocaleString()||'—'],['使用率',`${context.value.usage_percent||0}%`],['输入 / 输出 token（服务商）',context.value.usage?`${context.value.usage.prompt_tokens??'—'} / ${context.value.usage.completion_tokens??'—'}`:'未返回'],['用户 / 助手消息',`${data.value?.user_messages||0} / ${data.value?.assistant_messages||0}`],['最近压缩',context.value.compression?`${context.value.compression.before_tokens} → ${context.value.compression.after_tokens} tokens ≈`:'尚未压缩']]);
function exportSession(){const blob=new Blob([JSON.stringify(data.value,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=`session-${props.threadId}.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
defineExpose({show:async()=>{open.value=true;await load();},compact:async()=>{open.value=true;await compact();},exportSession:async()=>{open.value=true;await load();if(data.value)exportSession();}});
</script>
<style scoped>
.context-trigger{display:inline-flex;align-items:center;gap:4px;background:transparent;border:0;border-radius:7px;padding:4px;color:var(--muted);font-size:10px;white-space:nowrap;}.context-trigger:hover{background:var(--surface-2);}.context-trigger svg{width:22px;height:22px;fill:none;stroke-width:2;transform:rotate(-90deg);}.ring-track{stroke:var(--border);}.ring-value{stroke:var(--fg);}.context-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:12px;}.context-actions>span{flex:1;}.context-note{font-size:11px;color:var(--muted);line-height:1.7;margin:12px 0;}.context-stats{display:grid;grid-template-columns:1fr 1fr;gap:20px 32px;margin:24px 0;}.context-stats dt{font-size:11px;color:var(--muted);}.context-stats dd{font-size:13px;margin:6px 0 0;overflow-wrap:anywhere;}h3{font-size:12px;font-weight:500;margin-top:24px;}.context-bar{display:flex;gap:1px;height:7px;border-radius:4px;overflow:hidden;background:var(--border);}.context-bar .user{background:#3c9657;}.context-bar .assistant{background:#d38a48;}.context-bar .tool{background:#987029;}.context-bar .system{background:#85878c;}.context-tabs{display:flex;gap:8px;margin-top:22px;}.selected{background:var(--surface-2);}.context-messages{max-height:45dvh;overflow:auto;border:1px solid var(--border);border-radius:8px;}details{border-bottom:1px solid var(--border);padding:9px 12px;font-size:12px;}summary{cursor:pointer;overflow-wrap:anywhere;}summary small{color:var(--muted);margin-left:8px;}pre{max-height:360px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;font:11px/1.7 var(--font-mono);}@media(max-width:480px){.context-stats{gap:16px;}.context-trigger>span{display:none;}}
</style>

<template>
  <section v-if="events.length||active" class="execution-feed" aria-label="执行过程">
    <template v-for="event in display" :key="event.id">
      <MarkdownMessage v-if="event.kind==='text'||event.kind==='delta'" :content="event.title"/>
      <details v-else-if="event.kind==='tool'" class="execution-tool" :class="event.status">
        <summary><UiIcon :name="toolIcon(event)" :size="15"/><strong>{{toolLabel(event.title)}}</strong><span class="tool-target" :title="toolTarget(event)">{{toolTarget(event)}}</span><span v-if="event.status==='running'||event.status==='error'" class="tool-state">{{event.status==='running'?'执行中':'失败'}}</span><UiIcon name="chevron" :size="12" class="tool-chevron"/></summary>
        <div class="tool-detail"><pre v-if="event.arguments">{{prettyArguments(event)}}</pre><pre v-if="event.result">{{event.result}}</pre></div>
      </details>
    </template>
    <p v-if="active" class="execution-status"><UiIcon name="activity"/>{{stopping?'正在中止…':display.some(e=>e.status==='running')?'正在执行工具…':'思考中…'}}</p>
  </section>
</template>
<script setup lang="ts">
import {computed,onUnmounted,ref,watch} from 'vue';
import {request} from '../store/app';
import MarkdownMessage from './MarkdownMessage.vue';
const props=defineProps<{threadId:string;persona:string;active:boolean;stopping:boolean}>();
const emit=defineEmits<{(e:'run',id:string):void}>();
type Event={id:number;kind:string;title:string;call_id?:string;status?:string;arguments?:string;result?:string};
const events=ref<Event[]>([]);
function argumentsOf(event:Event):Record<string,unknown>{try{return JSON.parse(event.arguments||'{}');}catch{return {};}}
function toolLabel(name:string){return ({list_dir:'列出目录',read_file:'读取文件',write_file:'写入文件',search_memory:'检索记忆',add_memory:'保存记忆',todowrite:'更新计划',todoread:'读取计划',run_local_agent:'本机智能体',call_mcp:'MCP',run_skill:'技能'} as Record<string,string>)[name]||name;}
function toolTarget(event:Event){const args=argumentsOf(event);return String(args.path||args.command||args.query||args.skill_id||args.tool_name||args.agent||(event.title==='list_dir'?'.':''));}
function toolIcon(event:Event){if(event.status==='error')return 'security';if(event.status==='running')return 'activity';return event.title==='list_dir'?'folder':event.title==='read_file'?'logs':event.title==='write_file'?'edit':'check';}
function prettyArguments(event:Event){return JSON.stringify(argumentsOf(event),null,2);}
const display=computed(()=>events.value.filter((e,index,all)=>(props.active||e.kind==='tool'||((e.kind==='text'||e.kind==='delta')&&all.slice(index+1).some(next=>next.kind==='model')))&&(e.kind!=='text'||!all.slice(0,index).some(previous=>previous.kind==='delta'&&previous.title===e.title))&&(e.kind!=='tool'||!all.slice(index+1).some(next=>next.call_id===e.call_id))));
let timer:ReturnType<typeof setInterval>|undefined;let version=0;
let requestId=0;
async function poll(){const generation=version,id=++requestId;if(!props.threadId)return;try{const data=await request<{events:Event[];run_id:string}>('/api/execution?'+new URLSearchParams({thread_id:props.threadId,persona:props.persona}));if(generation!==version||id!==requestId)return;events.value=data.events||[];emit('run',data.run_id||'');}catch{}}
watch(()=>props.active,active=>{clearInterval(timer);if(active){events.value=[];version++;void poll();timer=setInterval(poll,300);}else void poll();},{immediate:true});
watch(()=>[props.threadId,props.persona],()=>{version++;events.value=[];emit('run','');});
onUnmounted(()=>{version++;clearInterval(timer);});
</script>
<style scoped>
.execution-feed{display:grid;gap:8px;font-size:13px;}.execution-tool{min-width:0;}.execution-tool summary{display:flex;align-items:center;gap:9px;cursor:pointer;padding:7px 0;list-style:none;min-width:0;}.execution-tool summary::-webkit-details-marker{display:none;}.execution-tool summary strong{font-weight:500;white-space:nowrap;}.tool-target{color:var(--muted);font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0;}.tool-state{font-size:11px;color:var(--muted);white-space:nowrap;}.error>summary{color:var(--danger);}.tool-chevron{color:var(--muted);flex-shrink:0;transition:transform 150ms;}.execution-tool[open] .tool-chevron{transform:rotate(180deg);}.tool-detail{margin:4px 0 10px;padding:12px 16px;border:1px solid var(--border);border-radius:9px;background:var(--code-bg);}.execution-tool pre{font:11px/1.7 var(--font-mono);max-height:300px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;}.execution-status{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:12px;}
</style>

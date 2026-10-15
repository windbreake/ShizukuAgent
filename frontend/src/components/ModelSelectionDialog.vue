<template>
 <Teleport to="body"><Transition name="dialog"><div v-if="visible" class="dialog-overlay" @click.self="cancel" @keydown.esc="cancel" @keydown.tab="trap">
  <section ref="panel" class="app-dialog selection-dialog" role="dialog" aria-modal="true" aria-labelledby="model-choice-title">
   <header><div><h2 id="model-choice-title">选择模型</h2><p>{{providerName}} · 勾选后加入配置，取消勾选后从配置移除。</p></div><button class="icon-btn" type="button" aria-label="刷新远程模型" :disabled="loading" @click="emit('refresh')"><RefreshCw :size="17" :class="{spinning:loading}"/></button></header>
   <div class="selection-search"><SearchField v-model="query" placeholder="搜索模型…"/><button type="button" @click="selectVisible">全选</button><button type="button" @click="draft=[]">全不选</button></div>
   <div class="selection-meta"><span>已选 {{draft.length}} / 共 {{items.length}}</span><label><input type="checkbox" v-model="onlySelected"/>只看已选</label></div>
   <ToastNotice :message="error"/>
   <div class="selection-list" :aria-busy="loading">
    <div v-if="loading && !items.length" class="selection-empty"><RefreshCw :size="20" class="spinning"/>正在读取提供商模型…</div>
    <template v-for="group in groups" :key="group.title"><div v-if="group.models.length" class="selection-group">{{group.title}}</div><label v-for="model in group.models" :key="model.id" class="selection-row"><input v-model="draft" type="checkbox" :value="model.id" :aria-label="model.id"/><span class="model-text"><strong>{{model.name||model.id}}</strong><small v-if="model.name && model.name!==model.id">{{model.id}}</small></span><span class="model-facts">{{facts(model)}}</span><span class="model-owner">{{model.owned_by||''}}</span></label></template>
    <p v-if="!loading && !filtered.length" class="selection-empty">{{query ? '没有匹配的模型' : '暂无远端模型，可保留本地模型或手动添加'}}</p>
   </div>
   <footer><button type="button" class="btn" :disabled="saving" @click="cancel">取消</button><button type="button" class="btn selection-apply" :disabled="saving || !draft.length" @click="emit('apply',draft.slice())">{{saving?'应用中…':'应用'}}</button></footer>
  </section>
 </div></Transition></Teleport>
</template>
<script setup lang="ts">
import {computed,nextTick,ref,watch} from 'vue';import {RefreshCw} from 'lucide-vue-next';import SearchField from './SearchField.vue';
export type DiscoveredModel={id:string;name?:string;owned_by?:string;context_length?:number;context_window?:number;max_output_tokens?:number;capabilities?:unknown;modalities?:unknown};
const props=withDefaults(defineProps<{visible:boolean;providerName:string;remote:DiscoveredModel[];local:DiscoveredModel[];selected:string[];loading?:boolean;saving?:boolean;error?:string}>(),{loading:false,saving:false,error:''});
const emit=defineEmits<{(e:'cancel'):void;(e:'refresh'):void;(e:'apply',models:string[]):void}>();
const draft=ref<string[]>([]),query=ref(''),onlySelected=ref(false),panel=ref<HTMLElement|null>(null);let previous:HTMLElement|null=null;
watch(()=>props.visible,async visible=>{if(visible){previous=document.activeElement as HTMLElement;draft.value=props.selected.slice();query.value='';onlySelected.value=false;await nextTick();panel.value?.querySelector<HTMLInputElement>('input[type=search]')?.focus();}else previous?.focus();});
const items=computed(()=>{const map=new Map<string,DiscoveredModel>();props.local.forEach(m=>map.set(m.id,m));props.remote.forEach(m=>map.set(m.id,{...map.get(m.id),...m}));return [...map.values()].sort((a,b)=>a.id.localeCompare(b.id));});
const filtered=computed(()=>items.value.filter(m=>(!onlySelected.value||draft.value.includes(m.id))&&`${m.id} ${m.name||''} ${m.owned_by||''}`.toLowerCase().includes(query.value.toLowerCase())));
const groups=computed(()=>{const remoteIds=new Set(props.remote.map(m=>m.id));return [{title:'不在提供商返回列表中',models:filtered.value.filter(m=>!remoteIds.has(m.id))},{title:'提供商返回的模型',models:filtered.value.filter(m=>remoteIds.has(m.id))}];});
function selectVisible(){draft.value=Array.from(new Set([...draft.value,...filtered.value.map(m=>m.id)]));}
function cancel(){if(!props.saving)emit('cancel');}
function facts(m:DiscoveredModel){const n=m.context_length||m.context_window;const size=n?(n>=1000000?`${Math.round(n/100000)/10}M`:`${Math.round(n/1000)}K`):'';const caps=Array.isArray(m.capabilities)?m.capabilities:[];const modes=m.modalities as {input?:string[]}|undefined;return [size,caps.includes('reasoning')?'推理':'',modes?.input?.includes('image')||caps.includes('vision')?'图片':''].filter(Boolean).join(' · ');}
function trap(event:KeyboardEvent){const nodes=Array.from(panel.value?.querySelectorAll<HTMLElement>('button:not(:disabled),input')||[]);if(!nodes.length)return;const first=nodes[0],last=nodes[nodes.length-1];if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}}
</script>
<style scoped>
.selection-dialog{background:var(--surface,#fff);color:var(--fg,#20242c);border:1px solid var(--border,#e7e9ed);box-shadow:0 24px 80px #0003;}
.dialog-overlay{position:fixed!important;inset:0!important;z-index:1000!important;display:flex!important;align-items:center!important;justify-content:center!important;background:rgb(15 18 25 / .4)!important;backdrop-filter:blur(3px);padding:24px;box-sizing:border-box;}
.selection-dialog{width:min(760px,92vw);padding:26px;border-radius:16px;max-height:88dvh;display:flex;flex-direction:column;overflow:hidden;}header{display:flex;justify-content:space-between;gap:20px;}h2{margin:0;font-size:18px;}header p{margin:8px 0 22px;font-size:12px;line-height:1.6;color:var(--muted);}.selection-search{display:flex;align-items:center;gap:14px;}.selection-search>.search-field{flex:1;}.selection-search>button{white-space:nowrap;font-size:12px;padding:7px 4px;}.selection-meta{display:flex;justify-content:space-between;align-items:center;margin:14px 0;color:var(--muted);font-size:12px;}.selection-meta label{display:flex;align-items:center;gap:6px;}.selection-list{height:360px;min-height:120px;overflow:auto;border:1px solid var(--border);border-radius:12px;}.selection-group{position:sticky;top:0;background:var(--bg-raised);color:var(--muted);padding:9px 14px;font-size:11px;}.selection-row{display:flex;align-items:center;gap:12px;padding:13px 14px;border-bottom:1px solid var(--border);cursor:pointer;transition:background 150ms;}.selection-row:hover{background:var(--bg-raised);}input[type=checkbox]{width:17px;height:17px;flex-shrink:0;accent-color:#f97316;}.model-text{flex:1;min-width:0;}.model-text strong{display:block;font-size:13px;font-weight:450;overflow-wrap:anywhere;}.model-text small{display:block;font-size:10px;margin-top:4px;color:var(--muted);}.model-facts,.model-owner{color:var(--muted);font-size:11px;}.model-owner{width:82px;text-align:right;overflow:hidden;text-overflow:ellipsis;}.selection-empty{display:flex;justify-content:center;align-items:center;gap:10px;padding:36px 16px;font-size:12px;color:var(--muted);}footer{display:flex;justify-content:flex-end;gap:10px;margin-top:22px;}.selection-apply{background:#f97316;border-color:#f97316;color:white;}.spinning{animation:discovery-spin 1s linear infinite;}@keyframes discovery-spin{to{transform:rotate(360deg)}}
@media(max-width:600px){.selection-dialog{padding:18px}.model-owner{display:none}.model-facts{max-width:90px}.selection-search{gap:7px}}
</style>

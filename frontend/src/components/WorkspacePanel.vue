<template>
  <aside class="workspace-panel">
    <header><button :class="{active:tab==='files'}" @click="tab='files';load()"><UiIcon name="folder"/>文件</button><button :class="{active:tab==='changes'}" @click="tab='changes';changes()">审查</button><span class="spacer"/><button title="刷新" @click="tab==='files'?load():changes()"><UiIcon name="refresh"/></button></header>
    <div class="open-toolbar"><UiSelect v-model="opener" label="打开方式" :options="[{value:'explorer',label:'文件资源管理器'},{value:'vscode',label:'VS Code'},{value:'cursor',label:'Cursor'},{value:'zed',label:'Zed'},{value:'powershell',label:'PowerShell'},{value:'sublime',label:'Sublime Text'}]"/><button class="btn" @click="open(selectedPath||path)"><UiIcon name="folder"/>打开</button><button class="btn" @click="copyPath"><UiIcon name="copy"/>复制路径</button></div>
    <ToastNotice :message="error"/>
    <template v-if="tab==='files'"><SearchField v-model="filter" placeholder="筛选文件"/><button class="btn btn-ghost" @click="parent">上一级</button><div class="file-list"><button v-for="entry in filtered" :key="entry.path" @click="choose(entry)"><UiIcon :name="entry.kind==='dir'?'folder':'logs'"/>{{entry.name}}</button></div><pre v-if="content" class="file-preview">{{content}}</pre><p v-else class="hint">点击文件预览，点击目录进入。</p></template>
    <template v-else><h3>{{lastTurn ? '上一轮变更（工作区快照差异）' : '工作区变更'}}</h3><button class="btn" @click="lastTurn=!lastTurn">{{lastTurn?'显示全部变更':'上一轮变更'}}</button><div v-if="!initialized" class="review-empty"><UiIcon name="gateway" :size="32"/><h3>无跟踪的变更</h3><p>在工作区跟踪和审查更改</p><button class="btn" @click="init">创建 Git 仓库</button></div><pre v-else>{{lastTurn ? turnDiff || '上一轮没有捕获到变更' : status || '工作区没有变更'}}{{lastTurn?'':'\n'+diff}}</pre></template>
    <details><summary>运行信息、记忆与集成</summary><slot/></details>
  </aside>
</template>
<script setup lang="ts">
import {computed,onMounted,ref} from 'vue';import {request} from '../store/app';import UiIcon from './UiIcon.vue';
import UiSelect from './UiSelect.vue';
import SearchField from './SearchField.vue';
defineProps<{turnDiff?:string}>();
const tab=ref('files'),path=ref('.'),root=ref(''),filter=ref(''),content=ref(''),selectedPath=ref(''),opener=ref('explorer'),error=ref(''),status=ref(''),diff=ref(''),initialized=ref(false),lastTurn=ref(false);
const entries=ref<{name:string;path:string;kind:string}[]>([]);const filtered=computed(()=>entries.value.filter(e=>e.name.toLowerCase().includes(filter.value.toLowerCase())));
async function attempt(fn:()=>Promise<void>){error.value='';try{await fn();}catch(e){error.value=e instanceof Error?e.message:'操作失败';}}
function load(){return attempt(async()=>{const data=await request<{root:string;entries:typeof entries.value}>(`/api/workbench/files?path=${encodeURIComponent(path.value)}`);root.value=data.root;entries.value=data.entries;});}
function choose(e:typeof entries.value[number]){if(e.kind==='dir'){path.value=e.path;selectedPath.value='';content.value='';void load();}else{selectedPath.value=e.path;void attempt(async()=>{const data=await request<{content:string}>(`/api/workbench/files?path=${encodeURIComponent(e.path)}`);content.value=data.content;});}}
function parent(){path.value=path.value.includes('/')?path.value.slice(0,path.value.lastIndexOf('/')):'.';void load();}
function changes(){return attempt(async()=>{const data=await request<{initialized:boolean;status:string;diff:string}>('/api/workbench/changes');initialized.value=data.initialized;status.value=data.status;diff.value=data.diff;});}
function init(){return attempt(async()=>{await request('/api/workbench/git/init',{method:'POST'});await changes();});}
function open(value:string){return attempt(async()=>{await request('/api/workbench/open',{method:'POST',body:JSON.stringify({path:value,opener:opener.value})});});}
function copyPath(){return attempt(async()=>{await navigator.clipboard.writeText(root.value+'/'+(selectedPath.value||path.value));});}
onMounted(load);
</script>
<style scoped>
.workspace-panel{min-width:0;}header button,.open-toolbar .btn{flex-shrink:0;white-space:nowrap;font-size:12px;}header button svg,.open-toolbar svg{flex-shrink:0;}header button{min-height:34px;}.open-toolbar>.ui-select{flex:1 1 160px;min-width:140px;}.open-toolbar>.btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;}.file-list button{min-width:0;overflow-wrap:anywhere;}.open-toolbar{row-gap:8px;}
.workspace-panel{min-height:0;overflow:auto;background:var(--bg);border:1px solid var(--border);border-radius:14px;padding:12px;}
header,.open-toolbar{display:flex;gap:6px;align-items:center;margin-bottom:16px;}header button{display:flex;gap:7px;align-items:center;padding:8px;border-radius:6px;}header button.active{background:var(--surface-2);}.spacer{flex:1}.open-toolbar{flex-wrap:wrap}.open-toolbar select{max-width:100%;font-size:12px}.file-list{display:grid;gap:3px;margin:12px 0}.file-list button{display:flex;gap:8px;align-items:center;text-align:left;padding:8px;border-radius:6px;font-size:12px}.file-list button:hover{background:var(--surface-2)}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:45vh}.review-empty{text-align:center;padding:50px 8px;color:var(--muted)}details{border-top:1px solid var(--border);padding-top:14px;margin-top:20px}summary{cursor:pointer;font-size:12px}
</style>

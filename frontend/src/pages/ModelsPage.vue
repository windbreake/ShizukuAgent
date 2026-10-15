<template>
  <section class="model-settings">
    <header class="settings-heading"><div><p class="eyebrow">ShizukuClaw / 连接</p><h1>提供商</h1><p>独立凭据、模型列表与会话选择。</p></div><RouterLink class="btn provider-add" to="/providers/new"><UiIcon name="plus"/>添加提供商</RouterLink></header>
    <nav class="model-tabs" aria-label="模型管理分类"><button v-for="tab in tabs" :key="tab.id" :class="{active:active===tab.id}" @click="active=tab.id"><UiIcon :name="tab.icon"/>{{tab.label}}</button><span class="spacer"/><RouterLink to="/monitoring" class="usage-link"><UiIcon name="activity"/>用量</RouterLink></nav>
    <label class="model-search"><UiIcon name="search"/><input v-model="query" :placeholder="active === 'providers' ? '搜索提供商或地址' : '搜索模型或分组'" aria-label="搜索模型配置"/><span>{{count}} 项</span></label>
    <ModelSelectionDialog :visible="Boolean(editingProvider)" :provider-name="String(appStore.providers[editingProvider]?.name || editingProvider)" :remote="remoteModels" :local="localModels" :selected="selection" :loading="fetching" :saving="saving" :error="selectionError" @cancel="editingProvider=''" @refresh="refreshSelection" @apply="applySelected"/>
    <div v-content-motion="active" class="model-tab-content">
    <template v-if="active==='providers'">
      <p class="section-intro">已连接的提供商 <span>{{Object.keys(appStore.providers).length}}</span></p>
      <div class="provider-rows"><div v-for="[id,provider] in providers" :key="id" class="provider-row"><span class="provider-avatar">{{String(provider.name||id).slice(0,1).toUpperCase()}}</span><div class="record-main"><strong>{{provider.name||id}}</strong><span class="record-url">{{provider.base_url||'尚未配置接口地址'}}</span></div><button class="icon-btn" :aria-label="`选择 ${provider.name||id} 的模型`" @click="editSelection(id)"><UiIcon name="models"/></button><RouterLink class="icon-btn" :aria-label="`编辑 ${provider.name||id}`" :to="`/providers/${encodeURIComponent(id)}`"><UiIcon name="edit"/></RouterLink><button class="icon-btn" :aria-label="`刷新 ${provider.name||id} 的模型`" :disabled="fetching" @click="discover(id)"><UiIcon name="refresh"/></button></div><p v-if="!providers.length" class="empty-settings">没有匹配的提供商。</p></div>
    </template>
    <template v-else-if="active==='models'">
      <p class="section-intro">可用模型 <span>{{models.length}}</span><RouterLink to="/config-editor?section=models">管理模型能力 <UiIcon name="chevron" :size="12"/></RouterLink></p>
      <div class="settings-list"><div v-for="model in models" :key="String(model.id)" class="setting-record"><span class="provider-mark"><UiIcon name="bot" :size="20"/></span><div class="record-main"><strong>{{model.name||model.model||model.id}}</strong><span class="record-url">{{appStore.providers[String(model.provider)]?.name||model.provider}} · {{model.model}}</span><div class="capabilities"><span v-for="cap in capabilities(model)" :key="cap">{{cap}}</span></div></div><button class="btn" :disabled="model.enabled===false||Boolean(model.auxiliary_only)" @click="appStore.currentModelId=String(model.id)"><UiIcon :name="appStore.currentModelId===model.id?'check':'plus'"/>{{appStore.currentModelId===model.id?'当前模型':'选用'}}</button></div><p v-if="!models.length" class="empty-settings">没有匹配的模型。</p></div>
    </template>
    <template v-else>
      <p class="section-intro">模型分组 <RouterLink to="/config-editor?section=groups">管理分组 <UiIcon name="chevron" :size="12"/></RouterLink></p>
      <div class="settings-list"><div v-for="[id,group] in groups" :key="id" class="setting-record"><span class="provider-mark"><UiIcon name="models" :size="20"/></span><div class="record-main"><strong>{{group.name||id}}</strong><span class="record-url">{{(group.models||[]).map(modelName).join('、')||'暂无成员'}}</span><span class="record-note">{{group.models?.length||0}} 个成员 · {{group.strategy||'fallback'}}</span></div><RouterLink class="btn btn-ghost" to="/config-editor?section=groups"><UiIcon name="edit"/>编辑</RouterLink></div><p v-if="!groups.length" class="empty-settings">没有匹配的分组。</p></div>
    </template>
    </div>
    <p v-if="appStore.statusError" class="notice-error">{{appStore.statusError}}</p>
    <p v-if="discoveryStatus" class="discovery-status" role="status">{{discoveryStatus}}</p>
    <footer class="settings-tip"><UiIcon name="security"/>密钥保存在本地配置中；状态标记仅表示已配置凭据，实际可用性以调用结果为准。</footer>
  </section>
</template>
<script setup lang="ts">
import { vContentMotion } from '../directives/contentMotion';
import {computed,onMounted,ref} from 'vue';
import {useAppStore} from '../store/app';
import UiIcon from '../components/UiIcon.vue';
import {request} from '../store/app';
import ModelSelectionDialog,{type DiscoveredModel} from '../components/ModelSelectionDialog.vue';
const appStore=useAppStore(),active=ref('providers'),query=ref('');
const tabs=[{id:'providers',label:'提供商',icon:'gateway'},{id:'models',label:'模型',icon:'bot'},{id:'groups',label:'分组',icon:'models'}];
const editingProvider=ref(''),selection=ref<string[]>([]),availableNames=ref<string[]>([]),manualModel=ref(''),selectionError=ref(''),saving=ref(false);
const fetching=ref(false),discoveryStatus=ref('');
const remoteModels=ref<DiscoveredModel[]>([]);
const localModels=computed(()=>modelsFor(editingProvider.value).map(m=>({id:String(m.model),name:String(m.name||m.model)})));
async function discover(id:string){editSelection(id);}
async function refreshSelection(){if(!editingProvider.value||fetching.value)return;const id=editingProvider.value;fetching.value=true;selectionError.value='';try{const data=await request<{models:DiscoveredModel[]}>(`/api/providers/${encodeURIComponent(id)}/models/remote`);if(editingProvider.value===id)remoteModels.value=data.models;}catch(e){selectionError.value=e instanceof Error?e.message:'读取失败';}finally{fetching.value=false;}}
async function applySelected(ids:string[]){selection.value=ids;await applyModels();}
async function importAll(id:string){fetching.value=true;discoveryStatus.value='正在读取并创建模型组…';try{const data=await request<{group_id:string}>(`/api/providers/${encodeURIComponent(id)}/models/import`,{method:'POST'});await appStore.loadStatus();discoveryStatus.value=`已创建模型组 ${data.group_id}，聊天中可直接选择具体模型。`;}catch(e){discoveryStatus.value=e instanceof Error?e.message:'导入失败';}finally{fetching.value=false;}}
function editSelection(id:string){editingProvider.value=id;remoteModels.value=[];availableNames.value=modelsFor(id).map(m=>String(m.model));selection.value=modelsFor(id).filter(m=>m.enabled!==false).map(m=>String(m.model));selectionError.value='';manualModel.value='';void refreshSelection();}
function addManual(){const name=manualModel.value.trim();if(name){if(!availableNames.value.includes(name))availableNames.value.push(name);if(!selection.value.includes(name))selection.value.push(name);manualModel.value='';}}
async function applyModels(){saving.value=true;try{const names=Object.fromEntries(selection.value.map(id=>[id,localModels.value.find(m=>m.id===id)?.name||remoteModels.value.find(m=>m.id===id)?.name||id]));await request(`/api/providers/${encodeURIComponent(editingProvider.value)}/models`,{method:'PUT',body:JSON.stringify({models:selection.value,model_names:names})});editingProvider.value='';await appStore.loadStatus();}catch(e){selectionError.value=e instanceof Error?e.message:'保存失败';}finally{saving.value=false;}}
const matches=(value:unknown)=>JSON.stringify(value).toLowerCase().includes(query.value.toLowerCase());
const providers=computed(()=>Object.entries(appStore.providers).filter(matches));
const models=computed(()=>appStore.models.filter(matches));
const groups=computed(()=>Object.entries(appStore.modelGroups).filter(matches));
const count=computed(()=>active.value==='providers'?providers.value.length:active.value==='models'?models.value.length:groups.value.length);
const modelsFor=(id:string)=>appStore.models.filter(m=>m.provider===id);
const modelName=(id:string)=>String(appStore.models.find(m=>m.id===id)?.model||id);
const capabilities=(model:Record<string,unknown>)=>Array.isArray(model.capabilities)?model.capabilities.map(String):[];
onMounted(()=>void appStore.loadStatus());
</script>
<style scoped>
.model-settings{max-width:1040px!important;width:100%;padding:44px 48px!important;box-sizing:border-box;}
.provider-rows{display:grid;gap:10px;}.provider-row{display:flex;align-items:center;gap:14px;padding:18px 22px;border:1px solid var(--border);border-radius:12px;min-height:76px;box-sizing:border-box;}.provider-avatar{width:38px;height:38px;display:grid;place-items:center;border:1px solid var(--border);border-radius:10px;font-size:14px;color:var(--muted);}.provider-add{background:#ff7914;color:white;border-color:#ff7914;}.provider-row .icon-btn{color:var(--muted);}.provider-row .icon-btn:hover{background:var(--surface-2);color:var(--fg);}
.settings-heading{display:flex;justify-content:space-between;align-items:flex-start;gap:24px;}.eyebrow{font-size:11px;color:var(--muted);margin:0 0 12px;}h1{font-size:24px;font-weight:600;letter-spacing:-.6px;margin:0 0 10px;}.settings-heading p:not(.eyebrow){font-size:13px;color:var(--muted);margin:0;}
.model-tabs{display:flex;align-items:center;gap:4px;border-bottom:1px solid var(--border);padding-bottom:10px;margin:28px 0 22px;}.model-tabs button{display:flex;align-items:center;gap:7px;padding:9px 13px;border:0;background:none;border-radius:7px;font-size:12px;color:var(--muted);}.model-tabs button.active{background:var(--surface-2);color:var(--fg);}.spacer{flex:1}.usage-link{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--muted);}
.model-search{display:flex;align-items:center;gap:10px;border:1px solid var(--border);border-radius:8px;padding:0 12px;height:38px;color:var(--muted);}.model-search input{flex:1;min-width:0;border:0!important;background:transparent!important;font-size:12px;box-shadow:none!important;}.model-search>span{font-size:10px;}
.section-intro{display:flex;align-items:center;gap:8px;margin:26px 0 12px;font-size:12px;font-weight:500;}.section-intro>span{font-size:10px;color:var(--muted);}.section-intro a{display:flex;gap:5px;align-items:center;margin-left:auto;color:var(--muted);font-size:11px;}
.settings-list{border:1px solid var(--border);border-radius:10px;overflow:hidden;}.setting-record{display:flex;align-items:center;gap:14px;padding:20px;background:var(--bg);}.setting-record+.setting-record{border-top:1px solid var(--border);}.provider-mark{display:grid;place-items:center;width:40px;height:40px;border:1px solid var(--border);border-radius:10px;background:var(--bg-raised);color:var(--muted);flex-shrink:0;}.record-main{flex:1;min-width:0;}.record-main strong{font-size:13px;font-weight:550;}.record-url{display:block;font-size:12px;color:var(--muted);margin-top:5px;overflow-wrap:anywhere;}.record-note{display:block;font-size:11px;color:var(--muted);margin-top:7px;}.connection-dot{width:6px;height:6px;border-radius:50%;background:var(--muted);}.connection-dot.configured{background:var(--success);}.capabilities{display:flex;gap:5px;margin-top:8px;}.capabilities span{font-size:10px;color:var(--muted);padding:2px 6px;border-radius:4px;background:var(--bg-raised);}.settings-tip{display:flex;gap:8px;align-items:flex-start;line-height:1.7;color:var(--muted);font-size:11px;margin-top:24px;}.empty-settings{text-align:center;padding:40px;color:var(--muted);font-size:12px;}.empty-settings h3{font-size:14px;color:var(--fg);}
@media(max-width:800px){.model-settings{padding:24px!important;}.settings-heading{flex-wrap:wrap;}.setting-record{flex-wrap:wrap;}}
</style>

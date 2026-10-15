<template>
  <section class="config-page">
    <header class="config-header">
      <div class="config-heading"><div><p class="eyebrow">设置 / 模型与连接</p><h1>连接与模型配置</h1><p>配置提供商、模型能力和辅助服务。</p></div><button type="button" class="btn btn-primary" :disabled="loading" @click="saveConfig"><UiIcon name="save"/>{{loading ? '保存中…' : '保存更改'}}</button></div>
    </header>

    <ToastNotice :message="status.message" :type="status.type"/>
    <nav class="config-sections" aria-label="配置分类"><button v-for="tab in tabs" :key="tab.id" :class="{active: section === tab.id}" type="button" @click="section = tab.id"><UiIcon :name="tab.icon"/>{{tab.label}}<span v-if="tab.id==='providers'">{{Object.keys(form.providers).length}}</span><span v-if="tab.id==='models'">{{Object.keys(form.models).length}}</span></button></nav>

    <form class="config-form" v-content-motion="section" @submit.prevent="saveConfig">
      <article class="panel" v-show="section === 'providers'">
        <SettingSection title="提供商配置" icon="gateway">
        <div class="panel-header">
          <div>
            <h2>提供商</h2>
            <p>每个提供商保存独立的接口地址与凭据。</p>
          </div>
            <button type="button" class="btn ghost" @click="addProvider"><UiIcon name="plus"/>添加提供商</button>
        </div>
        <div class="registry-list">
          <div v-for="(provider, id) in form.providers" :key="id" class="registry-card">
            <div class="registry-card-header"><div class="record-identity"><span class="record-icon"><UiIcon name="gateway"/></span><div><strong>{{provider.name || id}}</strong><small>{{id}}</small></div></div><button type="button" class="icon-btn destructive" :aria-label="`删除提供商 ${id}`" @click="removeProvider(id)"><UiIcon name="delete"/></button></div>
            <div class="field-grid two-col">
               <label>显示名称<input v-model="provider.name" type="text" placeholder="OpenAI" /></label>
              <label>类型<input v-model="provider.type" type="text" placeholder="openai_compatible" /></label>
              <label>Base URL<input v-model="provider.base_url" type="url" placeholder="https://api.openai.com/v1" /></label>
              <label>API Key<input v-model="provider.api_key" type="password" placeholder="留空或 *** 表示不修改" /></label>
            </div>
          </div>
        </div>
        </SettingSection>
      </article>

      <article class="panel" v-show="section === 'models'">
        <SettingSection title="模型配置" icon="models">
        <div class="panel-header">
          <div><h2>模型</h2><p>按实际能力分配工具；仅辅助模型不会进入对话选择列表。</p></div>
          <button type="button" class="btn ghost" @click="addModel"><UiIcon name="plus"/>添加模型</button>
        </div>
        <div class="registry-list">
          <div v-for="(model, id) in form.models" :key="id" class="registry-card">
            <div class="registry-card-header"><div class="record-identity"><span class="record-icon"><UiIcon name="bot"/></span><div><strong>{{model.name || id}}</strong><small>{{id}}</small></div></div><button type="button" class="icon-btn destructive" :aria-label="`删除模型 ${id}`" @click="removeModel(id)"><UiIcon name="delete"/></button></div>
            <div class="field-grid two-col">
              <label>模型显示名<input v-model="model.name" type="text" placeholder="GPT Agent" /></label>
              <label>Provider<select v-model="model.provider"><option v-for="(_, providerId) in form.providers" :key="providerId" :value="providerId">{{ providerId }}</option></select></label>
              <label>远端模型名<input v-model="model.model" type="text" placeholder="gpt-4o-mini" /></label>
              <label>能力<input v-model="model.capabilitiesText" type="text" placeholder="chat, tools, vision" /></label>
            </div>
            <div class="check-row">
              <label><input v-model="model.enabled" type="checkbox" />启用</label>
              <label><input v-model="model.auxiliary_only" type="checkbox" />仅辅助 API</label>
            </div>
          </div>
        </div>
        </SettingSection>
      </article>

      <article class="panel" v-show="section === 'groups'">
        <SettingSection title="模型分组配置" icon="models">
        <div class="panel-header">
          <div><h2>模型分组</h2><p>整理模型成员及默认配置；工作台可直接选择组内具体模型。</p></div>
          <button type="button" class="btn ghost" @click="addGroup"><UiIcon name="plus"/>添加分组</button>
        </div>
        <div class="field-grid two-col">
          <label>默认 Agent Group<select v-model="form.default_model_group"><option v-for="(_, groupId) in form.model_groups" :key="groupId" :value="groupId">{{ groupId }}</option></select></label>
        </div>
        <div class="registry-list">
          <div v-for="(group, id) in form.model_groups" :key="id" class="registry-card">
            <div class="registry-card-header"><div class="record-identity"><span class="record-icon"><UiIcon name="models"/></span><div><strong>{{group.name || id}}</strong><small>{{id}}</small></div></div><button type="button" class="icon-btn destructive" :aria-label="`删除分组 ${id}`" @click="removeGroup(id)"><UiIcon name="delete"/></button></div>
            <div class="field-grid two-col">
              <label>显示名<input v-model="group.name" type="text" placeholder="Default Agent" /></label>
              <label>用途<UiSelect v-model="group.purpose" label="分组用途" :options="[{value:'agent',label:'Agent'},{value:'auxiliary',label:'辅助 API'}]"/></label>
              <label>策略<UiSelect v-model="group.strategy" label="分组策略" :options="[{value:'fallback',label:'按顺序回退'},{value:'round_robin',label:'轮流选择'}]"/></label>
              <label>模型顺序<input v-model="group.modelsText" type="text" placeholder="primary, backup" /></label>
            </div>
          </div>
        </div>
        </SettingSection>
      </article>

      <article class="panel" v-show="section === 'auxiliary'">
        <SettingSection title="辅助 API 配置" icon="gateway">
        <div class="panel-header"><div><h2>辅助 APIs</h2><p>搜索、语音、生图等能力独立于 Agent 图运行。</p></div></div>
        <div class="registry-list">
          <div v-for="(api, id) in form.auxiliary_apis" :key="id" class="registry-card">
            <div class="registry-card-header"><strong>{{ id }}</strong><span class="muted">{{ api.enabled ? "已启用" : "未启用" }}</span></div>
            <div class="field-grid two-col">
              <label>绑定模型<select v-model="api.model"><option v-for="(_, modelId) in form.models" :key="modelId" :value="modelId">{{ modelId }}</option></select></label>
              <label>Endpoint<input v-model="api.endpoint" type="text" /></label>
            </div>
            <label class="check-row"><input v-model="api.enabled" type="checkbox" />启用此辅助 API</label>
          </div>
        </div>
        </SettingSection>
      </article>

      <article class="panel" v-show="section === 'storage'">
        <SettingSection title="数据库配置" icon="database">
        <h2><UiIcon name="database"/>数据库配置</h2>
        <div class="field-grid two-col">
          <label>主机地址<input v-model="form.database.host" type="text" /></label>
          <label>用户名<input v-model="form.database.user" type="text" /></label>
          <label>密码<input v-model="form.database.password" type="password" /></label>
          <label>数据库名<input v-model="form.database.database" type="text" /></label>
        </div>
        </SettingSection>
      </article>

      <article class="panel" v-show="section === 'character'">
        <SettingSection title="角色配置" icon="bot">
        <h2><UiIcon name="bot"/>角色配置</h2>
        <div class="field-grid two-col">
          <label>角色名称<input v-model="form.character.name" type="text" /></label>
          <label>角色性格<input v-model="form.character.personality" type="text" /></label>
          <label>哥哥QQ号<input v-model="form.character.brother_qqid" type="text" /></label>
          <label>身高<input v-model="form.character.height" type="text" /></label>
          <label>体重<input v-model="form.character.weight" type="text" /></label>
          <label>口癖(逗号分隔)<input v-model="form.character.catchphrases" type="text" /></label>
        </div>
        </SettingSection>
      </article>

      <div class="config-actions">
        <span>保存会应用所有分类中的更改。</span><button type="button" class="btn ghost" :disabled="loading" @click="loadCurrentConfig"><UiIcon name="refresh"/>重新加载</button>
      </div>
    </form>
  </section>
</template>

<script setup lang="ts">
import SettingSection from '../components/SettingSection.vue';
import { vContentMotion } from '../directives/contentMotion';
import { onMounted, reactive, ref, watch } from "vue";
import { useRoute } from 'vue-router';
import UiIcon from '../components/UiIcon.vue';
import UiSelect from '../components/UiSelect.vue';
const tabs=[{id:'providers',label:'提供商',icon:'gateway'},{id:'models',label:'模型',icon:'bot'},{id:'groups',label:'模型分组',icon:'models'},{id:'auxiliary',label:'辅助服务',icon:'voice'},{id:'storage',label:'存储',icon:'database'},{id:'character',label:'角色',icon:'memory'}];
const route=useRoute();
const section=ref(tabs.some(t=>t.id===route.query.section) ? String(route.query.section) : 'providers');
watch(()=>route.query.section,value=>{if(tabs.some(t=>t.id===value))section.value=String(value);});

type Provider = { name: string; type: string; base_url: string; api_key: string };
type Model = { provider: string; model: string; name: string; capabilitiesText: string; enabled: boolean; auxiliary_only: boolean };
type Group = { name: string; purpose: string; strategy: string; modelsText: string };
type AuxiliaryApi = { enabled: boolean; model: string; endpoint: string };
type FormData = {
  providers: Record<string, Provider>;
  models: Record<string, Model>;
  model_groups: Record<string, Group>;
  default_model_group: string;
  auxiliary_apis: Record<string, AuxiliaryApi>;
  database: { host: string; user: string; password: string; database: string };
  character: { name: string; personality: string; brother_qqid: string; height: string; weight: string; catchphrases: string };
};

const emptyForm = (): FormData => ({
  providers: {}, models: {}, model_groups: {}, default_model_group: "",
  auxiliary_apis: { search: { enabled: false, model: "", endpoint: "/chat/completions" }, speech: { enabled: false, model: "", endpoint: "/audio/speech" }, images: { enabled: false, model: "", endpoint: "/images/generations" } },
  database: { host: "", user: "", password: "", database: "" },
  character: { name: "", personality: "", brother_qqid: "", height: "", weight: "", catchphrases: "" }
});
const form = reactive<FormData>(emptyForm());
const loading = ref(false);
const status = reactive<{ type: "success" | "error"; message: string }>({ type: "success", message: "" });
const setStatus = (type: "success" | "error", message: string) => { status.type = type; status.message = message; };
const slug = (prefix: string, items: Record<string, unknown>) => {let index=1;while(`${prefix}-${index}` in items)index++;return `${prefix}-${index}`;};

const addProvider = () => { const id = slug("provider", form.providers); form.providers[id] = { name: id, type: "openai_compatible", base_url: "https://api.openai.com/v1", api_key: "" }; };
const removeProvider = (id: string) => { delete form.providers[id]; };
const addModel = () => { const id = slug("model", form.models); form.models[id] = { provider: Object.keys(form.providers)[0] || "", model: "", name: id, capabilitiesText: "chat, tools", enabled: true, auxiliary_only: false }; };
const removeModel = (id: string) => { delete form.models[id]; };
const addGroup = () => { const id = slug("group", form.model_groups); form.model_groups[id] = { name: id, purpose: "agent", strategy: "fallback", modelsText: Object.keys(form.models).join(", ") }; if (!form.default_model_group) form.default_model_group = id; };
const removeGroup = (id: string) => { delete form.model_groups[id]; if (form.default_model_group === id) form.default_model_group = Object.keys(form.model_groups)[0] || ""; };

const applyConfig = (incoming: any) => {
  const next = emptyForm();
  next.providers = Object.fromEntries(Object.entries(incoming.providers || {}).map(([id, raw]: [string, any]) => [id, { name: raw.name || id, type: raw.type || "openai_compatible", base_url: raw.base_url || "", api_key: "" }]));
  next.models = Object.fromEntries(Object.entries(incoming.models || {}).map(([id, raw]: [string, any]) => [id, { provider: raw.provider || "", model: raw.model || "", name: raw.name || id, capabilitiesText: (raw.capabilities || []).join(", "), enabled: raw.enabled !== false, auxiliary_only: raw.auxiliary_only === true }]));
  next.model_groups = Object.fromEntries(Object.entries(incoming.model_groups || {}).map(([id, raw]: [string, any]) => [id, { name: raw.name || id, purpose: raw.purpose || "agent", strategy: raw.strategy || "fallback", modelsText: (raw.models || []).join(", ") }]));
  next.default_model_group = incoming.default_model_group || Object.keys(next.model_groups)[0] || "";
  for (const [id, raw] of Object.entries(incoming.auxiliary_apis || {})) next.auxiliary_apis[id] = { enabled: (raw as any).enabled === true, model: (raw as any).model || "", endpoint: (raw as any).endpoint || "" };
  Object.assign(next.database, incoming.database || {}); Object.assign(next.character, incoming.character || {}); Object.assign(form, next);
};

const loadCurrentConfig = async () => {
  loading.value = true;
  try { const response = await fetch("/api/config"); if (!response.ok) throw new Error(`HTTP ${response.status}`); applyConfig(await response.json()); setStatus("success", "配置加载成功"); }
  catch (error) { setStatus("error", `加载配置失败: ${error instanceof Error ? error.message : "未知错误"}`); }
  finally { loading.value = false; }
};

const saveConfig = async () => {
  loading.value = true;
  try {
    const registry = {
      providers: Object.fromEntries(Object.entries(form.providers).map(([id, value]) => [id, { ...value }])),
      models: Object.fromEntries(Object.entries(form.models).map(([id, value]) => [id, { provider: value.provider, model: value.model, name: value.name, capabilities: value.capabilitiesText.split(",").map((item) => item.trim()).filter(Boolean), enabled: value.enabled, auxiliary_only: value.auxiliary_only }])),
      model_groups: Object.fromEntries(Object.entries(form.model_groups).map(([id, value]) => [id, { name: value.name, purpose: value.purpose, strategy: value.strategy, models: value.modelsText.split(",").map((item) => item.trim()).filter(Boolean) }])),
      default_model_group: form.default_model_group,
      auxiliary_apis: form.auxiliary_apis
    };
    const legacy = { database: form.database, character: form.character, llm: { model: form.models.primary?.model || Object.values(form.models)[0]?.model || "", base_url: form.providers.openai?.base_url || Object.values(form.providers)[0]?.base_url || "", api_key: form.providers.openai?.api_key || "***" } };
    const configResponse = await fetch("/api/config", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(legacy) });
    if (!configResponse.ok) throw new Error(`基础配置保存失败: HTTP ${configResponse.status}`);
    const response = await fetch("/api/model-registry", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(registry) });
    if (!response.ok) { const payload = await response.json().catch(() => ({})); throw new Error(payload.error || `HTTP ${response.status}`); }
    setStatus("success", "模型注册表和基础配置保存成功"); await loadCurrentConfig();
  } catch (error) { setStatus("error", `保存配置失败: ${error instanceof Error ? error.message : "未知错误"}`); }
  finally { loading.value = false; }
};

onMounted(loadCurrentConfig);
</script>
<style scoped>
.config-form>.panel:has(>.setting-section){padding:0!important;border:0;box-shadow:none;background:none;}
.config-page{width:100%;max-width:1040px!important;padding:44px 48px!important;box-sizing:border-box;}
.config-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:24px;}
.eyebrow{font-size:11px;color:var(--muted);margin:0 0 12px;}
h1{font-size:24px;font-weight:600;letter-spacing:-.6px;margin:0 0 10px;}
.config-header p:not(.eyebrow){font-size:13px;color:var(--muted);margin:0;line-height:1.7;}
.config-sections{display:flex;gap:3px;flex-wrap:wrap;margin:28px 0 32px;border-bottom:1px solid var(--border);padding-bottom:10px;}
.config-sections button{display:inline-flex;align-items:center;gap:7px;padding:9px 11px;border:0;border-radius:7px;color:var(--muted);font-size:12px;background:transparent;}
.config-sections button.active{background:var(--surface-2);color:var(--fg);}
.config-sections button span{font-size:10px;border-radius:4px;background:var(--bg);padding:2px 5px;}
.config-form{display:block;}
.config-form>.panel{padding:0!important;border:0!important;border-radius:0;background:none;box-shadow:none;}
.panel-header{display:flex;justify-content:space-between;align-items:flex-start;gap:20px;margin-bottom:24px;}
h2{font-size:15px;margin:0 0 6px;}
.panel p{margin:0;font-size:12px;color:var(--muted);}
.registry-list{display:grid;gap:20px;}
.registry-card{padding:0!important;background:none;box-shadow:none;border:1px solid var(--border);border-radius:10px;overflow:hidden;}
.registry-card-header{display:flex;justify-content:space-between;align-items:center;padding:16px 20px;border-bottom:1px solid var(--border);background:var(--bg-raised);}
.record-identity{display:flex;align-items:center;gap:12px;}.record-icon{display:grid;place-items:center;width:34px;height:34px;border:1px solid var(--border);background:var(--surface);border-radius:8px;color:var(--muted);}.record-identity strong{display:block;font-size:13px;font-weight:550;}.record-identity small{display:block;font:10px var(--font-mono);color:var(--muted);margin-top:4px;}
.destructive{color:var(--muted);}.destructive:hover{color:var(--danger);background:color-mix(in srgb,var(--danger) 10%,transparent);}
.field-grid{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px 24px;padding:22px;}
.field-grid>label{display:flex!important;flex-direction:column;align-items:stretch;gap:8px;min-width:0;font-size:12px;color:var(--muted);}
.field-grid input,.field-grid select{display:block;width:100%;height:38px;min-width:0;box-sizing:border-box;font:13px var(--font-body);color:var(--fg);background:var(--bg);border:1px solid var(--border);border-radius:7px;}
.check-row{display:flex;align-items:center;gap:24px;padding:0 22px 20px;font-size:12px;}.check-row label{display:inline-flex;align-items:center;gap:7px;}
.config-actions{display:flex;align-items:center;justify-content:space-between;border-top:1px solid var(--border);margin-top:28px;padding-top:18px;font-size:11px;color:var(--muted);}
.config-status{display:flex;align-items:center;gap:8px;margin-top:18px;padding:10px 12px;font-size:12px;border-radius:7px;background:var(--bg-raised);}.config-status.success{color:var(--success)}.config-status.error{color:var(--danger)}
@media(max-width:800px){.config-page{padding:24px!important;}.field-grid{grid-template-columns:1fr;}.config-heading{flex-wrap:wrap;}}
</style>

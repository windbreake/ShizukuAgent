<template>
  <div class="runtime-settings settings-redesign">
    <header><p class="kicker">Settings</p><h1>设置</h1><p class="hint">管理连接、技能、人格和语音资源。</p></header>
    <nav class="section-tabs" aria-label="设置分类"><button v-for="item in categories" :key="item.id" :class="{active:category===item.id}" @click="category=item.id"><UiIcon :name="item.icon"/>{{item.label}}</button></nav>
    <ToastNotice :message="message" :type="failed?'error':'success'"/>
    <div class="settings-grid" v-content-motion="category">
      <SettingSection v-show="show('mcp')" title="MCP 服务器" icon="mcp" :count="appStore.mcpServers.length">
        <p>编辑连接配置或直接修改 servers.json，保存后重新加载。</p>
        <div class="section-actions"><button class="btn" @click="newMcp"><UiIcon name="plus"/>新增服务器</button><button class="btn" @click="edit('mcp','','servers.json')"><UiIcon name="edit"/>编辑 JSON</button></div>
        <div v-for="server in appStore.mcpServers" :key="server.id" class="setting-row">
          <div class="row-label"><strong><UiIcon name="mcp"/> {{server.name}}</strong><small>{{server.type}} · {{server.id}}</small></div>
          <div class="row-actions"><button class="switch" role="switch" :aria-label="`启用 ${server.name}`" :aria-checked="Boolean(server.enabled)" @click="perform(async()=>{await request(`/api/systems/mcp/servers/${encodeURIComponent(server.id!)}`,{method:'PUT',body:JSON.stringify({enabled:!server.enabled})});await appStore.loadStatus();})"/><button class="icon-btn" :aria-label="`编辑 ${server.name}`" @click="editMcp(server.id!)"><UiIcon name="edit"/></button><button class="icon-btn" :aria-label="`删除 ${server.name}`" @click="removeMcp(server.id!)"><UiIcon name="delete"/></button></div>
        </div>
        <SettingsDialog :visible="mcpEditing" :title="mcpId?'编辑 MCP 服务器':'新增 MCP 服务器'" @close="mcpEditing=false">
          <form @submit.prevent="saveMcp"><label class="field">ID<input v-model="mcpForm.id" required :disabled="Boolean(mcpId)"/></label><label class="field">名称<input v-model="mcpForm.name" required/></label><label class="field">类型<select v-model="mcpForm.type"><option value="stdio">stdio</option><option value="http">http</option><option value="internal">internal</option></select></label><template v-if="mcpForm.type==='stdio'"><label class="field">命令<input v-model="mcpForm.command" required/></label><label class="field">参数（JSON 数组）<textarea v-model="mcpArgs" rows="2"/></label></template><label v-if="mcpForm.type==='http'" class="field">URL<input v-model="mcpForm.url" type="url" required/></label><label class="field">请求头（JSON 对象）<textarea v-model="mcpHeaders" rows="3"/></label><button class="btn btn-primary" :disabled="busy"><UiIcon name="save"/>保存服务器</button></form>
        </SettingsDialog>
      </SettingSection>

      <SettingSection v-show="show('skills')" title="技能策略" icon="skills" :count="appStore.skills.length">
        <p>直接编辑 SKILL.md 中的说明与提示词，或调整调用权限。</p>
        <RouterLink class="btn" to="/extensions"><UiIcon name="plus"/>安装技能</RouterLink>
        <div v-for="skill in appStore.skills" :key="skill.skill_id" class="setting-row"><div class="row-label"><strong>{{skill.name}}</strong><small>{{skill.skill_id}}</small></div><div class="row-actions"><button class="icon-btn" :aria-label="`编辑 ${skill.name} 的 SKILL.md`" @click="edit('skill',skill.skill_id!,'SKILL.md')"><UiIcon name="edit"/></button><button class="btn btn-ghost" @click="skillPolicy(skill.skill_id!,{allow_model_invocation:skill.policy?.allow_model_invocation===false})">模型调用：{{skill.policy?.allow_model_invocation===false?'关':'开'}}</button><button class="switch" role="switch" :aria-label="`启用技能 ${skill.name}`" :aria-checked="Boolean(skill.policy?.enabled)" @click="skillPolicy(skill.skill_id!,{enabled:!skill.policy?.enabled})"/></div></div><p v-if="!appStore.skills.length">暂无已安装技能。</p>
      </SettingSection>

      <SettingSection v-show="show('personas')" title="人格" icon="bot" :count="personas.length">
        <p>persona.json 保存人设与提示词，PERSONA.md 保存人格说明。</p>
        <div v-for="persona in personas" :key="persona.filename" class="setting-row"><div class="row-label"><strong>{{persona.name}}</strong><small>{{persona.filename}}</small></div><div class="row-actions"><button class="btn" @click="edit('persona',persona.filename.replace(/\.json$/,''),'persona.json')"><UiIcon name="edit"/>JSON</button><button class="btn" @click="edit('persona',persona.filename.replace(/\.json$/,''),'PERSONA.md')"><UiIcon name="logs"/>MD</button><button class="btn" :disabled="persona.is_active" @click="activate(persona.filename)">{{persona.is_active?'当前人格':'激活'}}</button></div></div>
        <button class="btn" @click="personaCreating=true"><UiIcon name="plus"/>创建人格</button>
        <SettingsDialog :visible="personaCreating" title="创建人格" @close="personaCreating=false"><form @submit.prevent="createPersona"><label class="field">标识<input v-model="personaId" required pattern="[A-Za-z0-9_-]+" placeholder="my-persona"/></label><label class="field">名称<input v-model="personaName" required/></label><label class="field">性格与描述<textarea v-model="personaDescription" rows="3"/></label><p v-if="failed" class="notice-error">{{message}}</p><footer><button type="button" class="btn" @click="personaCreating=false">取消</button><button class="btn btn-primary" :disabled="busy"><UiIcon name="plus"/>创建并编辑 JSON</button></footer></form></SettingsDialog>
      </SettingSection>

      <SettingSection v-show="show('permissions')" title="工作模式" icon="security">
        <div class="setting-row"><span>沙箱执行</span><button class="switch" role="switch" aria-label="沙箱执行" :aria-checked="sandbox" @click="toggleSandbox"/></div>
        <details class="inline-editor"><summary><UiIcon name="security"/>设置工作模式密码</summary><form @submit.prevent="savePassword"><label class="field">新密码<input v-model="password" type="password" minlength="6" required/></label><label class="field">当前密码（首次可留空）<input v-model="currentPassword" type="password"/></label><button class="btn" :disabled="busy">保存密码</button></form></details>
      </SettingSection>

      <SettingSection v-show="show('plugins')" title="插件管理" icon="plugins" :count="plugins.length">
        <button class="btn" @click="perform(loadPlugins)"><UiIcon name="refresh"/>刷新插件</button><div v-for="plugin in plugins" :key="plugin.name" class="setting-row"><div class="row-label"><strong>{{plugin.name}}</strong><small>{{plugin.version}}</small></div><button class="switch" role="switch" :aria-label="`启用插件 ${plugin.name}`" :aria-checked="Boolean(plugin.policy?.enabled)" @click="togglePlugin(plugin)"/></div><p v-if="!plugins.length">暂无插件。</p>
      </SettingSection>

      <SettingSection v-show="show('media')" title="TTS 语音资源" icon="voice" :count="voiceAssets.length">
        <p>导入语音模型、配置和参考音频所在的 ZIP 压缩包或文件夹。资源保存在本地；语音合成仍需接入匹配的 TTS 引擎。</p>
        <div class="setting-row"><span>语音回复</span><button class="switch" role="switch" aria-label="语音回复" :aria-checked="ttsEnabled" :disabled="busy" @click="saveTts(!ttsEnabled)"/></div>
        <label class="field voice-picker">目标语言<select v-model="ttsLanguage" @change="saveTts(ttsEnabled)"><option value="zh">中文</option><option value="ja">日本語</option><option value="en">English</option></select></label>
        <div class="section-actions"><label class="btn import-button"><UiIcon name="upload"/>导入 ZIP<input type="file" accept=".zip" :disabled="busy" @change="importVoice($event,false)"/></label><label class="btn import-button"><UiIcon name="folder"/>导入文件夹<input type="file" webkitdirectory multiple :disabled="busy" @change="importVoice($event,true)"/></label></div>
        <label class="field voice-picker">当前资源<select v-model="voiceAsset" @change="selectVoice"><option value="">未选择资源</option><option v-for="asset in voiceAssets" :key="asset.id" :value="asset.id">{{asset.name}}（{{asset.files}} 个文件）</option></select></label>
        <p v-if="busy">正在处理，请稍候…</p>
      </SettingSection>
    </div>
    <ResourceEditor :resource="resource" @close="resource=null" @saved="perform(reload)"/>
    <ConfirmModal :visible="Boolean(deletingMcp)" title="删除 MCP 服务器" :message="`确认删除 ${deletingMcp}？`" @cancel="deletingMcp=''" @confirm="confirmRemoveMcp"/>
  </div>
</template>
<script setup lang="ts">
import {onMounted,ref,watch} from 'vue';
import {notify} from '../store/notifications';
import {zipSync} from 'fflate';
import {useAppStore,request} from '../store/app';
import SettingSection from '../components/SettingSection.vue';
import ResourceEditor from '../components/ResourceEditor.vue';
import ConfirmModal from '../components/ConfirmModal.vue';
import SettingsDialog from '../components/SettingsDialog.vue';
import {vContentMotion} from '../directives/contentMotion';
const appStore=useAppStore(),category=ref('mcp'),busy=ref(false),failed=ref(false),message=ref('');
watch(message,value=>{if(value){notify(value,failed.value?'error':'success');message.value='';}});
const categories=[{id:'all',label:'全部设置',icon:'settings'},{id:'mcp',label:'MCP 集成',icon:'mcp'},{id:'skills',label:'技能',icon:'skills'},{id:'personas',label:'人格',icon:'bot'},{id:'permissions',label:'权限与执行',icon:'security'},{id:'plugins',label:'插件',icon:'plugins'},{id:'media',label:'语音资源',icon:'voice'}];
const show=(id:string)=>category.value==='all'||category.value===id;
const resource=ref<{kind:string;key:string;filename:string}|null>(null);
function edit(kind:string,key:string,filename:string){resource.value={kind,key,filename};}
async function perform(action:()=>Promise<unknown>){if(busy.value)return;busy.value=true;failed.value=false;message.value='';try{await action();}catch(e){failed.value=true;message.value=e instanceof Error?e.message:String(e);}finally{busy.value=false;}}
const personas=ref<{filename:string;name:string;is_active:boolean}[]>([]),personaId=ref(''),personaName=ref(''),personaDescription=ref('');
const personaCreating=ref(false);
async function loadPersonas(){const data=await request<{personas:typeof personas.value}>('/api/personas');personas.value=data.personas||[];}
function createPersona(){return perform(async()=>{if(personas.value.some(p=>p.filename===personaId.value+'.json'))throw new Error('人格标识已存在');await request('/api/personas',{method:'POST',body:JSON.stringify({filename:personaId.value+'.json',content:{meta:{name:personaName.value,description:personaDescription.value},character:{name:personaName.value,personality:personaDescription.value},system_prompt:{template:'你是{name}，性格是{personality}。'}}})});await loadPersonas();personaCreating.value=false;edit('persona',personaId.value,'persona.json');});}
function activate(filename:string){return perform(async()=>{await request('/api/personas/activate',{method:'POST',body:JSON.stringify({filename})});appStore.currentPersona=filename.replace(/\.json$/,'');await loadPersonas();});}
const mcpId=ref(''),mcpEditing=ref(false),mcpArgs=ref('[]'),mcpHeaders=ref('{}'),mcpForm=ref({id:'',name:'',type:'stdio',command:'',url:''}),deletingMcp=ref('');
function newMcp(){mcpId.value='';mcpForm.value={id:'',name:'',type:'stdio',command:'',url:''};mcpArgs.value='[]';mcpHeaders.value='{}';mcpEditing.value=true;}
function editMcp(id:string){void perform(async()=>{const data=await request<{data:Record<string,unknown>}>(`/api/systems/mcp/servers/${encodeURIComponent(id)}`);const server=data.data;mcpId.value=id;mcpForm.value={id,name:String(server.name||id),type:String(server.type||'stdio'),command:String(server.command||''),url:String(server.url||'')};mcpArgs.value=JSON.stringify(server.args||[],null,2);mcpHeaders.value=JSON.stringify(server.headers||{},null,2);mcpEditing.value=true;});}
function saveMcp(){return perform(async()=>{const args=JSON.parse(mcpArgs.value),headers=JSON.parse(mcpHeaders.value);if(!Array.isArray(args)||!args.every(x=>typeof x==='string'))throw new Error('参数必须为字符串数组');if(!headers||Array.isArray(headers)||typeof headers!=='object'||!Object.values(headers).every(x=>typeof x==='string'))throw new Error('请求头必须为字符串键值对象');await request('/api/systems/mcp/servers'+(mcpId.value?'/'+encodeURIComponent(mcpId.value):''),{method:mcpId.value?'PUT':'POST',body:JSON.stringify({...mcpForm.value,args,headers})});await appStore.loadStatus();mcpEditing.value=false;message.value='MCP 服务器已保存';});}
function removeMcp(id:string){deletingMcp.value=id;}
function confirmRemoveMcp(){const id=deletingMcp.value;deletingMcp.value='';void perform(async()=>{await request(`/api/systems/mcp/servers/${encodeURIComponent(id)}`,{method:'DELETE'});await appStore.loadStatus();});}
function skillPolicy(id:string,policy:Record<string,boolean>){return perform(async()=>{await request('/api/skills/policy',{method:'POST',body:JSON.stringify({skill_id:id,policy})});await appStore.loadStatus();});}
const sandbox=ref(false),password=ref(''),currentPassword=ref('');
function toggleSandbox(){return perform(async()=>{const data=await request<{enabled:boolean}>('/api/work_mode/toggle',{method:'POST',body:JSON.stringify({enable:!sandbox.value,scope:'sandbox'})});sandbox.value=data.enabled;});}
function savePassword(){return perform(async()=>{await request('/api/work_mode/password',{method:'POST',body:JSON.stringify({password:password.value,current_password:currentPassword.value})});password.value='';currentPassword.value='';message.value='密码已保存';});}
type Plugin={name:string;version?:string;policy?:{enabled?:boolean}};
const plugins=ref<Plugin[]>([]);
async function loadPlugins(){const data=await request<{status:{plugins?:Plugin[];loaded_plugins?:string[]}}>('/api/plugins/status');plugins.value=data.status?.plugins||data.status?.loaded_plugins?.map(name=>({name,policy:{enabled:true}}))||[];}
function togglePlugin(plugin:Plugin){return perform(async()=>{await request('/api/plugins/policy',{method:'POST',body:JSON.stringify({plugin_name:plugin.name,policy:{enabled:!plugin.policy?.enabled}})});await loadPlugins();});}
const voiceAssets=ref<{id:string;name:string;files:number}[]>([]),voiceAsset=ref('');
const ttsEnabled=ref(false),ttsLanguage=ref('ja');
function saveTts(enabled:boolean){return perform(async()=>{await request('/api/tts/settings',{method:'POST',body:JSON.stringify({voice_reply_enabled:enabled,target_language:ttsLanguage.value})});ttsEnabled.value=enabled;message.value='语音设置已保存';});}
async function loadVoice(){const data=await request<{items:typeof voiceAssets.value;selected:string}>('/api/settings-resources/tts');voiceAssets.value=data.items||[];voiceAsset.value=data.selected||'';}
async function saveVoice(){await request('/api/settings-resources/tts',{method:'PUT',body:JSON.stringify({asset:voiceAsset.value})});}
function selectVoice(){return perform(saveVoice);}
function importVoice(event:Event,folder:boolean){const input=event.target as HTMLInputElement;const files=Array.from(input.files||[]);if(!files.length)return;void perform(async()=>{let blob:Blob,name=files[0].name;if(folder){const entries:Record<string,Uint8Array>={};let total=0;for(const file of files){total+=file.size;if(total>256*1024*1024)throw new Error('文件夹不能超过 256 MB');entries[file.webkitRelativePath||file.name]=new Uint8Array(await file.arrayBuffer());}const packed=zipSync(entries,{level:0});blob=new Blob([packed.buffer as ArrayBuffer]);name=(files[0].webkitRelativePath.split('/')[0]||'voice')+'.zip';}else{if(files[0].size>256*1024*1024)throw new Error('压缩包不能超过 256 MB');blob=files[0];}const response=await fetch('/api/settings-resources/tts/import?filename='+encodeURIComponent(name),{method:'POST',body:blob});const data=await response.json();if(!response.ok)throw new Error(data.detail||'导入失败');await loadVoice();voiceAsset.value=data.id;await saveVoice();message.value='语音资源已导入并选中';}).finally(()=>input.value='');}
async function reload(){await Promise.all([appStore.loadStatus(),loadPersonas(),loadPlugins(),loadVoice()]);const [work,tts]=await Promise.all([request<{sandbox_enabled:boolean}>('/api/work_mode/status'),request<{voice_reply_enabled:boolean;target_language:string}>('/api/tts/settings')]);sandbox.value=Boolean(work.sandbox_enabled);ttsEnabled.value=Boolean(tts.voice_reply_enabled);ttsLanguage.value=tts.target_language||'ja';}
onMounted(()=>perform(reload));
</script>
<style scoped>
.settings-redesign{display:grid;gap:20px;max-width:1100px;margin:auto;}.settings-redesign h1{margin:6px 0 12px;font-size:24px;}.settings-redesign .settings-grid{display:grid;grid-template-columns:1fr;gap:14px;}.section-actions{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0;}.inline-editor{margin-top:18px;border-top:1px solid var(--border);padding-top:16px;}.inline-editor summary{display:flex;align-items:center;gap:8px;cursor:pointer;font-size:12px;color:var(--muted);}.inline-editor form{margin-top:16px;}.settings-feedback{font-size:12px;color:var(--success);}.voice-picker{margin-top:16px;}.import-button{position:relative;display:inline-flex;align-items:center;gap:7px;cursor:pointer;}.import-button input{position:absolute;inset:0;opacity:0;cursor:pointer;width:100%;}.section-tabs button{display:flex;align-items:center;gap:6px;}
</style>

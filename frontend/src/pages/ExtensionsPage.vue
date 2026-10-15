<template>
  <div class="extension-page">
    <p class="kicker">WORKSPACE / EXTENSIONS</p><h1>扩展与本机智能体</h1>
    <p class="lede">管理技能来源、连接已安装的智能体，并查看运行观测状态。</p>
    <div class="section-tabs"><button v-for="tab in tabs" :key="tab.id" :class="{active: active === tab.id}" @click="active = tab.id">{{tab.label}}</button></div>
    <p v-if="error" class="notice-error" role="alert">{{error}}</p>
    <div v-content-motion="active">
    <section v-if="active === 'agents'" class="card">
      <h2>本机智能体</h2><p>检测 OpenCode、Codex、Claude、OpenClaw 等 CLI。</p>
      <button class="btn" :disabled="busy" @click="detectAgents">{{busy ? '检测中…' : '检测已安装智能体'}}</button>
      <div v-for="agent in agents" :key="String(agent.id)" class="row-item"><div><strong>{{agent.name}}</strong><p>{{agent.path || '未安装'}}</p></div><span class="pill">{{agent.installed ? '已安装' : '未安装'}}</span></div>
      <form @submit.prevent="runAgent"><label class="field">智能体<select v-model="selectedAgent" required><option value="">请选择</option><option v-for="agent in agents.filter(a=>a.installed)" :key="String(agent.id)" :value="String(agent.id)">{{agent.name}}</option></select></label><label class="field">任务<textarea v-model="prompt" required rows="4" placeholder="描述要交给本机智能体的任务"/></label><button class="btn btn-primary" :disabled="busy || !selectedAgent">运行任务</button></form>
      <pre v-if="output">{{output}}</pre>
    </section>
    <section v-if="active === 'market'" class="card">
      <h2>技能市场</h2><form @submit.prevent="searchSkills"><label class="field">搜索关键词<input v-model="query" placeholder="例如 filesystem、search"/></label><button class="btn" :disabled="busy">搜索 GitHub 技能</button></form>
      <div v-for="(skill,i) in results" :key="i" class="row-item"><div><strong>{{skill.name || skill.id}}</strong><p>{{skill.description}}</p><a v-if="skill.external_url" :href="String(skill.external_url)" target="_blank" rel="noopener">查看来源</a></div></div>
      <h3>从链接安装</h3><form @submit.prevent="installSkill"><label class="field">技能 URL<input v-model="skillUrl" required type="url" placeholder="GitHub 仓库或 SKILL.md 链接"/></label><button class="btn btn-primary" :disabled="busy">安装技能</button></form><p>{{installStatus}}</p>
    </section>
    <section v-if="active === 'observe'" class="card"><h2>运行观测</h2><button class="btn" :disabled="busy" @click="loadObservability">刷新状态</button><pre v-if="observability">{{observability}}</pre><p v-else>点击刷新查看已配置的观测插件。</p></section>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref } from 'vue';
import { vContentMotion } from '../directives/contentMotion';
import { request } from '../store/app';
const tabs = [{id:'agents',label:'本机智能体'},{id:'market',label:'技能市场'},{id:'observe',label:'运行观测'}];
const active = ref('agents'), busy = ref(false), error = ref('');
const agents = ref<Record<string,unknown>[]>([]), selectedAgent = ref(''), prompt = ref(''), output = ref('');
const query = ref(''), skillUrl = ref(''), installStatus = ref(''), observability = ref('');
const results = ref<Record<string,unknown>[]>([]);
async function perform(action: ()=>Promise<void>) { busy.value=true;error.value='';try{await action();}catch(e){error.value=e instanceof Error?e.message:'操作失败';}finally{busy.value=false;} }
function detectAgents(){return perform(async()=>{const data=await request<{agents:Record<string,unknown>[]}>('/api/systems/agents');agents.value=data.agents||[];});}
function runAgent(){return perform(async()=>{const data=await request<Record<string,unknown>>(`/api/systems/agents/${encodeURIComponent(selectedAgent.value)}/run`,{method:'POST',body:JSON.stringify({prompt:prompt.value})});output.value=String(data.output||JSON.stringify(data,null,2));});}
function searchSkills(){return perform(async()=>{const data=await request<{items?:Record<string,unknown>[]}>(`/api/skills/market/github?query=${encodeURIComponent(query.value)}`);results.value=data.items||[];});}
function installSkill(){return perform(async()=>{const data=await request<{message?:string}>('/api/skills/market/github/install',{method:'POST',body:JSON.stringify({url:skillUrl.value})});installStatus.value=data.message||'安装完成';});}
function loadObservability(){return perform(async()=>{observability.value=JSON.stringify(await request('/api/observability'),null,2);});}
</script>

<template>
  <div class="workspace with-inspector" :class="{'inspector-hidden':!inspectorOpen,'sessions-hidden':!sessionsOpen}" :style="{'--session-width':sessionsOpen?sessionWidth+'px':'0px','--inspector-width':inspectorWidth+'px',height:'100%'}">
    <aside v-if="sessionsOpen" class="pane sessions">
      <div class="pane-head">
        <h2>会话</h2>
        <span class="spacer"></span>
        <button class="icon-btn" type="button" title="新会话" :disabled="appStore.loading" @click="newSession">
          <UiIcon name="plus"/>
        </button>
      </div>
      <div style="padding: 8px 8px 0">
        <SearchField v-model="sessionQuery" placeholder="搜索会话"/>
      </div>
      <div class="pane-body">
        <div class="session-list">
          <button
            v-for="session in filteredSessions"
            :key="session.id"
            class="session"
            :class="{ active: session.id === currentSessionId }"
            type="button"
            @click="activateSession(session.id)"
          >
            <span class="t">{{ session.title }}</span>
            <time>{{ session.time }}</time>
            <span class="s">{{ sessionPreview(session) }}</span>
          </button>
          <p v-if="!filteredSessions.length" class="hint" style="padding: 10px">
            暂无会话，点击上方 + 新建。
          </p>
        </div>
      </div>
      <div class="pane-foot">
        <RouterLink class="nav-item" to="/settings">
          <span class="ico" aria-hidden="true">
            <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3" /><path d="M12 3v2M12 19v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M3 12h2M19 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
          </span>
          <span>设置<small>技能、人格、MCP、权限</small></span>
        </RouterLink>
        <RouterLink class="nav-item" to="/models">
          <span class="ico" aria-hidden="true">
            <svg viewBox="0 0 24 24"><path d="M4 8l8-4 8 4-8 4z" /><path d="M4 12l8 4 8-4M4 16l8 4 8-4" /></svg>
          </span>
          <span>模型与模型组<small>提供商、分组、用量</small></span>
        </RouterLink>
      </div>
    </aside>

    <div v-if="sessionsOpen" class="pane-resizer left-resizer" role="separator" aria-label="调整会话栏宽度" tabindex="0" @pointerdown="startResize($event,'left')" @keydown.left.prevent="sessionWidth=Math.max(190,sessionWidth-20)" @keydown.right.prevent="sessionWidth=Math.min(420,sessionWidth+20)"/>
    <main class="pane chat-col">
      <div class="pane-head">
        <h2>{{ currentSessionTitle }}</h2>
        <button class="icon-btn" title="隐藏或显示会话列表" aria-label="隐藏或显示会话列表" @click="sessionsOpen=!sessionsOpen"><UiIcon name="chat"/></button>
        <span class="spacer"></span>
        <span class="pill ok">{{ appStore.lastEngine || "LangGraph" }}</span>
        <button class="icon-btn" title="收起或展开右侧栏" @click="inspectorOpen=!inspectorOpen"><UiIcon name="folder"/></button>
      </div>
      <div class="pane-body" ref="threadScrollEl">
        <div class="thread">
          <article v-for="(item, index) in messages" :key="index" :class="['msg', item.role === 'user' ? 'user' : 'agent']">
            <div class="who">{{ item.role === "user" ? "你" : `Shizuku · ${item.model || "agent"}` }}</div>
            <div class="bubble">{{ item.content }}</div>
            <div class="message-actions"><button type="button" title="复制消息" @click="copyMessage(item.content)"><UiIcon name="copy" :size="14"/>复制</button><button v-if="item.role === 'user'" type="button" @click="composerText = item.content"><UiIcon name="edit" :size="14"/>重新编辑</button></div>
            <details v-if="item.trace && item.trace.length" class="trace">
              <summary>
                <span class="pill">工具</span>
                {{ item.trace.length }} 次调用
              </summary>
              <pre>{{ formatTrace(item.trace) }}</pre>
            </details>
          </article>
          <div v-if="!messages.length" class="empty-chat" key="empty">
            <div class="empty-mark">雫</div>
            <h1>从一个想法开始</h1>
            <p>对话、整理知识，或让 Shizuku 帮你完成工作。</p>
            <div class="quick-prompts"><button class="btn" @click="composerText = '帮我梳理一个项目的结构'">分析项目</button><button class="btn" @click="composerText = '帮我整理今天的工作计划'">整理计划</button><button class="btn" @click="composerText = '查找与当前任务相关的记忆'">检索记忆</button></div>
          </div>
          <p v-if="appStore.loading" class="hint" key="pending">正在处理请求…</p>
        </div>
      </div>

      <div class="composer-wrap">
        <TaskPlan :thread-id="currentSessionId" :persona="appStore.currentPersona" :active="appStore.loading"/>
        <ApprovalBar :thread-id="currentSessionId" :persona="appStore.currentPersona" :active="appStore.loading || shellPending"/>
        <form class="composer" @submit.prevent="sendMessage">
          <textarea
            ref="composerInput"
            v-model="composerText"
            rows="3"
            placeholder="随便问点什么， / 可查看命令， @ 可添加上下文…"
              @keydown="handleComposerKey"
          />
          <div class="composer-toolbar">
            <div class="composer-picker">
              <button class="composer-add" type="button" aria-label="添加上下文或命令" :aria-expanded="addMenu" @click="addMenu = !addMenu"><UiIcon name="plus" :size="19"/></button>
              <Transition name="popover"><div v-if="addMenu" class="composer-popover action-popover" role="menu" @keydown.esc="addMenu = false">
                <button type="button" @click="commandOpen=true;addMenu=false"><UiIcon name="terminal"/>命令 <span>/</span></button>
                <button type="button" @click="insertComposer('@')"><UiIcon name="memory"/>上下文 <span>@</span></button>
                <button type="button" @click="shellMode=true;addMenu=false;composerInput?.focus()"><UiIcon name="terminal"/>Shell 命令 <span>!</span></button>
              </div></Transition>
            </div>
            <ComposerPicker v-model="appStore.currentModelId" label="模型" :options="modelOptions" manage="/models"/>
            <ComposerPicker v-model="appStore.reasoningEffort" label="强度" :options="[{value:'default',label:'Default'},{value:'low',label:'Low'},{value:'medium',label:'Medium'},{value:'high',label:'High'}]"/>
            <ComposerPicker v-model="appStore.currentPersona" label="人格" :options="personaPickerOptions" manage="/settings"/>
            <ComposerPicker :model-value="workModeLabel" label="工作模式" :options="[{value:'full',label:'完全控制'},{value:'chat',label:'对话模式'},{value:'sandbox',label:'安全模式'}]" @update:model-value="changeWorkMode"/>
            <span class="spacer"/>
            <button class="send" type="submit" aria-label="发送" :disabled="appStore.loading || !composerText.trim()"><UiIcon name="arrowUp" :size="19"/></button>
          </div>
          <Transition name="popover"><div v-if="commandOpen" class="composer-command-list" role="dialog" aria-label="命令面板" @keydown.esc="commandOpen=false"><input v-model="commandQuery" placeholder="搜索命令" aria-label="搜索命令"/><button v-for="command in filteredCommands" :key="command.name" type="button" @click="executeCommand(command.name)">{{command.name}} · {{command.label}}</button></div></Transition>
          <button v-if="shellMode" class="shell-indicator" type="button" @click="shellMode=false">Shell · 点击退出 / Esc</button>
          <Transition name="popover"><div v-if="composerText === '@'" class="composer-command-list"><button type="button" @click="insertComposer('请检索与当前任务相关的长期记忆：')">长期记忆</button><button type="button" @click="insertComposer('请使用已启用的技能分析以下问题：')">已启用技能</button></div></Transition>
        </form>
        <p class="hint">
          {{ workModeHint }}
          <template v-if="appStore.lastActiveModel"> · 当前模型: {{ appStore.lastActiveModel }}</template>
        </p>
        <p v-if="interactionError || appStore.statusError" class="notice-error">{{ interactionError || appStore.statusError }}</p>
      </div>
    </main>

    <div v-if="inspectorOpen" class="pane-resizer right-resizer" role="separator" aria-label="调整文件栏宽度" tabindex="0" @pointerdown="startResize($event,'right')" @keydown.left.prevent="inspectorWidth=Math.min(700,inspectorWidth+20)" @keydown.right.prevent="inspectorWidth=Math.max(260,inspectorWidth-20)"/>
    <WorkspacePanel v-if="inspectorOpen" :turn-diff="turnDiff"><aside class="pane inspector runtime-details">
      <div class="pane-head">
        <h2>运行信息</h2>
        <span class="spacer"></span>
        <button class="icon-btn" type="button" title="刷新" @click="refresh">
          <svg viewBox="0 0 24 24"><path d="M4 4v6h6" /><path d="M20 20v-6h-6" /><path d="M5 15a7 7 0 0 0 12.5 2M19 9A7 7 0 0 0 6.5 7" /></svg>
        </button>
      </div>
      <div class="pane-body" style="padding: 10px; display: grid; gap: 10px; align-content: start">
        <div class="card">
          <h2><UiIcon name="security"/>工作模式</h2>
          <p>文件与本机工具的执行策略。</p>
          <div style="display: flex; align-items: center; gap: 10px">
            <button
              class="switch"
              type="button"
              role="switch"
              :aria-checked="appStore.workModeEnabled"
              @click="toggleWorkMode"
            />
            <span class="hint">{{ appStore.workModeEnabled ? "已启用" : "已禁用" }}</span>
          </div>
        </div>

        <div class="card">
          <h2><UiIcon name="memory"/>永久记忆</h2>
          <button type="button" class="btn btn-ghost btn-block" @click="loadMemory">
            <UiIcon name="search"/>查看记忆
          </button>
          <details v-if="memoryVisible" class="memory-viewer">
            <summary>记忆内容</summary>
            <pre class="memory-content">{{ appStore.memoryText || "暂无记忆。" }}</pre>
          </details>
          <form style="display: grid; gap: 6px" @submit.prevent="saveMemory">
            <textarea
              v-model="memoryInput"
              rows="2"
              placeholder="输入要记住的内容..."
              class="mono"
              style="border: 1px solid var(--border); border-radius: 6px; background: var(--bg); color: var(--fg); padding: 8px; font-size: 12px"
            />
            <button type="submit" class="btn btn-ghost btn-block" :disabled="memorySaving">
              <UiIcon name="plus"/>{{ memorySaving ? "保存中..." : "添加到记忆" }}
            </button>
            <p v-if="memoryMessage" class="hint" :style="{ color: memoryError ? 'var(--danger)' : 'var(--success)' }">
              {{ memoryMessage }}
            </p>
          </form>
        </div>

        <div class="card">
          <h2><UiIcon name="skills"/>可用技能</h2>
          <p v-if="!appStore.skills.length">暂无已安装技能。</p>
          <ul v-else style="padding-left: 18px; margin: 0; font-size: 13px; color: var(--muted)">
            <li v-for="skill in appStore.skills" :key="skill.skill_id">{{ skill.name }}</li>
          </ul>
        </div>

        <div class="card">
          <h2><UiIcon name="mcp"/>MCP 服务器</h2>
          <p v-if="!appStore.mcpServers.length">暂无 MCP 服务器。</p>
          <div v-for="server in appStore.mcpServers" :key="server.id" style="display: flex; justify-content: space-between; font-size: 13px">
            <span>{{ server.name }}</span>
            <span class="badge" :class="server.enabled ? 'on' : 'off'">
              {{ server.enabled ? server.status || "enabled" : "disabled" }}
            </span>
          </div>
        </div>
      </div>
    </aside></WorkspacePanel>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import { useAppStore, type ChatResponse } from "../store/app";
import ComposerPicker from '../components/ComposerPicker.vue';
import UiIcon from '../components/UiIcon.vue';
import WorkspacePanel from '../components/WorkspacePanel.vue';
import SearchField from '../components/SearchField.vue';
import ApprovalBar from '../components/ApprovalBar.vue';
import TaskPlan from '../components/TaskPlan.vue';
import {request} from '../store/app';
import {useRouter} from 'vue-router';

type MessageItem = {
  role: "user" | "agent";
  content: string;
  trace?: ChatResponse["trace"];
  model?: string;
};

type SessionItem = {
  id: string;
  title: string;
  time: string;
  preview: string;
  persona?: string;
};

const STORAGE_KEY = "sc_sessions";

const appStore = useAppStore();
const { personas } = storeToRefs(appStore);

const composerText = ref("");
const sessionQuery = ref("");
const messages = ref<MessageItem[]>([]);
const sessions = ref<SessionItem[]>([]);
const currentSessionId = ref("");
const memoryVisible = ref(false);
const memoryInput = ref("");
const memorySaving = ref(false);
const memoryMessage = ref("");
const memoryError = ref(false);
const threadScrollEl = ref<HTMLElement | null>(null);
const interactionError = ref('');
const shellPending=ref(false);
const router=useRouter(),inspectorOpen=ref(true),shellMode=ref(false),commandOpen=ref(false),commandQuery=ref(''),turnDiff=ref('');
const sessionsOpen=ref(localStorage.getItem('sc-sessions-open')!=='false'),sessionWidth=ref(Number(localStorage.getItem('sc-session-width'))||254),inspectorWidth=ref(Number(localStorage.getItem('sc-inspector-width'))||360);
watch(sessionsOpen,value=>localStorage.setItem('sc-sessions-open',String(value)));
function startResize(event:PointerEvent,side:string){event.preventDefault();const target=event.currentTarget as HTMLElement;target.setPointerCapture(event.pointerId);const start=event.clientX,width=side==='left'?sessionWidth.value:inspectorWidth.value;document.body.style.cursor='col-resize';document.body.style.userSelect='none';function move(e:PointerEvent){if(side==='left')sessionWidth.value=Math.max(190,Math.min(420,width+e.clientX-start));else inspectorWidth.value=Math.max(260,Math.min(700,width+start-e.clientX));}function stop(){target.removeEventListener('pointermove',move);target.removeEventListener('pointerup',stop);target.removeEventListener('pointercancel',stop);document.body.style.cursor='';document.body.style.userSelect='';localStorage.setItem('sc-session-width',String(sessionWidth.value));localStorage.setItem('sc-inspector-width',String(inspectorWidth.value));}target.addEventListener('pointermove',move);target.addEventListener('pointerup',stop);target.addEventListener('pointercancel',stop);}
const commands=[{name:'/new',label:'新会话'},{name:'/clear',label:'清空当前会话上下文'},{name:'/models',label:'选择模型'},{name:'/settings',label:'运行时设置'},{name:'/shell',label:'进入 Shell 模式'},{name:'/files',label:'打开文件侧栏'},{name:'/help',label:'查看命令'}];
const filteredCommands=computed(()=>commands.filter(c=>(c.name+c.label).toLowerCase().includes(commandQuery.value.toLowerCase())));
const modelOptions=computed(()=>appStore.models.filter(m=>m.enabled!==false&&!m.auxiliary_only).map(m=>({value:String(m.id),label:String(m.name||m.model||m.id),group:String(appStore.providers[String(m.provider)]?.name||m.provider||'提供商')})).sort((a,b)=>a.group.localeCompare(b.group)));
async function executeCommand(name:string){commandOpen.value=false;composerText.value='';if(name==='/new'){newSession();return;}if(name==='/clear'){await request('/api/workbench/session/reset',{method:'POST',body:JSON.stringify({thread_id:currentSessionId.value||`persona:${appStore.currentPersona}`,persona:appStore.currentPersona})});messages.value=[];return;}if(name==='/models'){await router.push('/models');return;}if(name==='/settings'){await router.push('/settings');return;}if(name==='/shell'){shellMode.value=true;return;}if(name==='/files'){inspectorOpen.value=true;return;}commandOpen.value=true;}
const addMenu=ref(false);
const composerInput=ref<HTMLTextAreaElement|null>(null);
const groupOptions=computed(()=>Object.entries(appStore.modelGroups).map(([value,group])=>({value,label:group.name||value})));
const personaPickerOptions=computed(()=>personaOptions.value.map(p=>({value:p.skill_id||'shizuku',label:p.name||p.skill_id||'Shizuku'})));
function insertComposer(text:string){composerText.value=text;addMenu.value=false;void nextTick(()=>composerInput.value?.focus());}

const personaOptions = computed(() =>
  personas.value.length
    ? personas.value
    : [{ skill_id: "shizuku", name: "Shizuku" }],
);

const filteredSessions = computed(() => {
  const q = sessionQuery.value.trim().toLowerCase();
  if (!q) {
    return sessions.value;
  }
  return sessions.value.filter(
    (s) =>
      s.title.toLowerCase().includes(q) || s.preview.toLowerCase().includes(q),
  );
});

const currentSessionTitle = computed(() => {
  const session = sessions.value.find((s) => s.id === currentSessionId.value);
  return session ? session.title : "新会话";
});

const workModeLabel = computed(() =>
  appStore.workMode,
);

const workModeHint = computed(() => {
  if (appStore.workModeEnabled) {
    return "完全控制：可读写工作区与本机工具。Shift+Enter 换行。";
  }
  return "对话模式：仅对话与检索，文件工具在策略层受限。Shift+Enter 换行。";
});

function loadSessions() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    sessions.value = raw ? (JSON.parse(raw) as SessionItem[]) : [];
  } catch {
    sessions.value = [];
  }
}

function persistSessions() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions.value));
}

function makeSession(title: string, preview: string): SessionItem {
  const now = new Date();
  return {
    id: `s_${now.getTime()}`,
    title: title || "新会话",
    time: `${now.getHours()}:${String(now.getMinutes()).padStart(2, "0")}`,
    preview,
    persona: appStore.currentPersona,
  };
}

function newSession() {
  if (appStore.loading) return;
  currentSessionId.value = "";
  messages.value = [];
  composerText.value = "";
}

function activateSession(id: string) {
  if (appStore.loading) return;
  currentSessionId.value = id;
  const session = sessions.value.find((s) => s.id === id);
  if (session) {
    if(session.persona && session.persona !== appStore.currentPersona){appStore.currentPersona=session.persona;return;}
    try { messages.value = JSON.parse(session.preview) as MessageItem[]; } catch { messages.value = []; }
  }
}

function scrollToBottom() {
  void nextTick(() => {
    if (threadScrollEl.value) {
      threadScrollEl.value.scrollTop = threadScrollEl.value.scrollHeight;
    }
  });
}

async function sendMessage() {
  const text = composerText.value.trim();
  if (!text || appStore.loading) {
    return;
  }
  if(text.startsWith('/')){const name=text.split(/\s/)[0];if(commands.some(c=>c.name===name)){await executeCommand(name);}else{interactionError.value='未知命令，请使用 /help';commandOpen.value=true;}return;}
  if(shellMode.value||text.startsWith('!')){if(shellPending.value)return;if(!currentSessionId.value)currentSessionId.value=`shell_${Date.now()}`;shellPending.value=true;try{const command=text.startsWith('!')?text.slice(1).trim():text;const result=await request<{stdout:string;stderr:string;exit_code:number}>('/api/workbench/shell',{method:'POST',body:JSON.stringify({command,thread_id:currentSessionId.value,persona:appStore.currentPersona})});messages.value.push({role:'user',content:'$ '+command},{role:'agent',content:`Shell · exit ${result.exit_code}\n${result.stdout||''}${result.stderr||''}`});composerText.value='';}catch(e){interactionError.value=e instanceof Error?e.message:'Shell 执行失败';}finally{shellPending.value=false;}return;}
  messages.value.push({ role: "user", content: text });
  composerText.value = "";
  scrollToBottom();
  const requestPersona = appStore.currentPersona;
  try {
    if (!currentSessionId.value) {
      const session = makeSession(text.slice(0, 24), JSON.stringify(messages.value));
      currentSessionId.value = session.id;
      sessions.value.unshift(session);
    }
    const before=await request<{diff?:string}>('/api/workbench/changes').catch(()=>({diff:''}));
    const data = await appStore.chat(text, currentSessionId.value);
    const after=await request<{diff?:string}>('/api/workbench/changes').catch(()=>({diff:''}));
    turnDiff.value=after.diff!==before.diff?after.diff||'变更已清除':'';
    messages.value.push({
      role: "agent",
      content: data.reply || "（空回复）",
      trace: data.trace || [],
      model: data.active_model,
    });
    if (!currentSessionId.value) {
      const session = makeSession(
        text.slice(0, 24),
        JSON.stringify(messages.value),
      );
      currentSessionId.value = session.id;
      sessions.value.unshift(session);
    } else {
      const session = sessions.value.find((s) => s.id === currentSessionId.value);
      if (session) {
        session.preview = JSON.stringify(messages.value);
        session.title = messages.value[0]?.content.slice(0, 24) || session.title;
      }
    }
    persistSessions();
  } catch (error) {
    const err = error instanceof Error ? error.message : "发送失败";
    messages.value.push({ role: "agent", content: `发送失败: ${err}` });
  }
  scrollToBottom();
}

function formatTrace(trace: ChatResponse["trace"]) {
  if (!trace) {
    return "";
  }
  return trace
    .map((t) => `- ${t.tool} ok=${t.ok} -> ${String(t.result || "").slice(0, 300)}`)
    .join("\n");
}

async function toggleWorkMode() {
  const next = !appStore.workModeEnabled;
  try { await appStore.toggleWorkMode(next); interactionError.value = ''; }
  catch (error) { interactionError.value = error instanceof Error ? error.message : '切换失败'; }
}

async function onWorkModeChange(event: Event) {
  const value = (event.target as HTMLSelectElement).value;
  await changeWorkMode(value);
}
async function changeWorkMode(value: string) {
  try {
    await appStore.setWorkMode(value);
    interactionError.value = '';
  } catch (error) { interactionError.value = error instanceof Error ? error.message : '切换失败'; }
}

function sessionPreview(session: SessionItem) {
  try { const items = JSON.parse(session.preview) as MessageItem[]; return items.at(-1)?.content.slice(0, 60) || ''; }
  catch { return session.preview.slice(0, 60); }
}
async function copyMessage(text: string) {
  try { await navigator.clipboard.writeText(text); }
  catch { interactionError.value = '复制失败，请检查浏览器剪贴板权限'; }
}
function handleComposerKey(event: KeyboardEvent) {
  if(event.key==='Escape'){commandOpen.value=false;addMenu.value=false;shellMode.value=false;return;}
  if(event.key==='/' && !composerText.value){event.preventDefault();commandOpen.value=true;commandQuery.value='';return;}
  if(event.key==='!' && !composerText.value){event.preventDefault();shellMode.value=true;return;}
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); void sendMessage(); }
}
function globalEscape(event:KeyboardEvent){if(event.key==='Escape'){commandOpen.value=false;addMenu.value=false;}}
onUnmounted(()=>document.removeEventListener('keydown',globalEscape));

async function loadMemory() {
  memoryVisible.value = true;
  await appStore.loadMemory();
}

async function saveMemory() {
  const content = memoryInput.value.trim();
  if (!content) {
    return;
  }
  memorySaving.value = true;
  memoryMessage.value = "";
  memoryError.value = false;
  try {
    await appStore.addMemory(content);
    memoryMessage.value = "已添加到长期记忆。";
    memoryInput.value = "";
    await appStore.loadMemory();
  } catch (error) {
    memoryError.value = true;
    memoryMessage.value = error instanceof Error ? error.message : "保存失败";
  } finally {
    memorySaving.value = false;
  }
}

async function refresh() {
  await appStore.loadStatus();
  await appStore.loadMemory();
}

watch(messages, scrollToBottom);
watch(()=>appStore.currentPersona,async(persona)=>{if(appStore.loading)return;try{const data=await request<{messages:{role:string;content:string}[]}>(`/api/workbench/session?persona=${encodeURIComponent(persona)}`);messages.value=(data.messages||[]).map(m=>({role:m.role==='user'?'user':'agent',content:m.content}));currentSessionId.value=`persona:${persona}`;await appStore.loadMemory();}catch(e){interactionError.value=e instanceof Error?e.message:'人格上下文加载失败';}});

onMounted(() => {
  document.addEventListener('keydown',globalEscape);
  loadSessions();
  if (sessions.value.length) {
    activateSession(sessions.value[0].id);
  }
  void appStore.loadStatus();
});
</script>
<style scoped>
.workspace.with-inspector{display:flex!important;flex-direction:row;align-items:stretch;flex-wrap:nowrap;overflow:hidden;box-sizing:border-box;width:100%;height:100%;gap:0;padding:10px;}
.workspace.with-inspector>.sessions{display:flex;flex:0 0 var(--session-width,254px);width:var(--session-width,254px);min-width:0;min-height:0;}
.workspace.with-inspector>.pane-resizer{flex:0 0 6px;width:6px;min-height:0;}
.workspace.with-inspector>.chat-col{flex:1 1 0%;min-width:0;min-height:0;width:0;height:100%;}
.workspace.with-inspector>:deep(.workspace-panel){flex:0 0 var(--inspector-width,360px);width:var(--inspector-width,360px);min-width:0;min-height:0;box-sizing:border-box;height:100%;}
@media(max-width:950px){.workspace.with-inspector>:deep(.workspace-panel),.workspace.with-inspector>.right-resizer{display:none;}.workspace.with-inspector>.sessions{flex-basis:200px;width:200px;}}
@media(max-width:650px){.workspace.with-inspector>.sessions,.workspace.with-inspector>.left-resizer{display:none;}}
/* Own the layout locally: legacy global flex rules cannot collapse this control. */
.composer-wrap{flex:0 0 auto;padding:12px 24px 18px;min-width:0;}
.chat-col>.pane-body{flex:1 1 0%;min-height:0;overflow:auto;}
.chat-col .thread{display:flex;flex-direction:column;justify-content:flex-start;align-items:stretch;width:100%;max-width:960px;margin:0 auto;padding:28px 32px;box-sizing:border-box;gap:26px;}
.chat-col .msg{display:flex;flex-direction:column;flex:0 0 auto;gap:5px;width:100%;margin:0;}
.chat-col .msg.user{align-items:flex-end;max-width:100%;}
.chat-col .msg.agent{align-items:flex-start;}
.chat-col .msg.user .bubble{max-width:78%;}
.chat-col .msg.agent .bubble{width:100%;max-width:100%;}
.chat-col .who{margin-bottom:4px!important;}
.chat-col .message-actions{margin-top:3px;}
.chat-col .composer-wrap{width:100%;max-width:960px;align-self:center;box-sizing:border-box;padding:8px 32px 16px;}
.chat-col .composer-wrap>.hint{white-space:normal;margin:8px 0 0;font-size:10px;}
.composer{display:grid!important;grid-template-columns:minmax(0,1fr)!important;grid-template-rows:auto auto;align-items:stretch!important;justify-items:stretch;gap:10px;width:100%;min-width:0;box-sizing:border-box;border:1px solid var(--border);border-radius:14px;padding:16px 12px 10px;max-height:240px;}
.composer>textarea{grid-row:1;grid-column:1;width:100%!important;min-width:0;max-width:100%;min-height:56px;height:64px;max-height:160px;box-sizing:border-box;flex:none!important;resize:none;border:0!important;padding:4px 9px;background:transparent!important;font:400 14px/1.65 var(--font-body);}
.composer-toolbar{grid-row:2;grid-column:1;display:flex!important;flex-direction:row!important;align-items:center;justify-content:flex-start;flex-wrap:nowrap;width:100%;min-width:0;gap:3px;}
.composer-toolbar>.spacer{display:block;flex:1 1 auto;min-width:8px;}
.composer-add{width:32px;height:32px;display:grid;place-items:center;flex:0 0 32px;padding:0;border:0;border-radius:7px;color:var(--muted);}
.composer-toolbar>.send{width:34px;height:34px;flex:0 0 34px;padding:0;display:grid;place-items:center;border-radius:9px;background:var(--fg);color:var(--bg);box-shadow:0 1px 3px #0002;}
.composer :deep(svg){width:16px;height:16px;fill:none;stroke:currentColor;flex-shrink:0;}
.composer-add :deep(svg),.send :deep(svg){width:19px;height:19px;}
.message-actions button{display:inline-flex;align-items:center;gap:5px;}
.action-popover{position:absolute!important;left:0;bottom:calc(100% + 10px);z-index:100;display:flex;flex-direction:column;min-width:220px;padding:5px;border:1px solid var(--border);border-radius:10px;background:var(--surface);box-shadow:0 8px 24px #0002;}
.action-popover button{display:flex;align-items:center;justify-content:flex-start;gap:9px;width:100%;height:38px;padding:0 12px;text-align:left;background:transparent;border:0;border-radius:6px;font-size:13px;}
.action-popover button:hover{background:var(--surface-2);}
.action-popover button span{margin-left:auto;color:var(--muted);}
.composer-add:hover,.composer-add[aria-expanded=true]{background:var(--surface-2);}
.card h2{display:flex;align-items:center;gap:8px;font-size:13px;}
@media(max-width:1100px){.composer-toolbar :deep(.composer-control){max-width:150px;font-size:12px;}.composer-toolbar :deep(.composer-control>svg:first-child){display:none;}}
@media(max-width:700px){.chat-col .thread{padding:20px 16px;}.chat-col .composer-wrap{padding:8px 16px 12px;}.composer-toolbar{flex-wrap:wrap;}.composer-toolbar :deep(.composer-control){max-width:120px;}}
</style>

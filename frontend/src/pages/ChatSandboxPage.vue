<template>
  <div ref="workspaceEl" class="workspace with-inspector" :class="{'inspector-hidden':!inspectorOpen,'sessions-hidden':!sessionsOpen,'sessions-drawer':sessionsDrawer,'inspector-drawer':inspectorDrawer}" :style="{'--session-width':layoutWidths.sessions+'px','--inspector-width':layoutWidths.inspector+'px',height:'100%'}">
    <button v-if="drawerOpen" class="drawer-backdrop" aria-label="关闭侧栏" @click="closeDrawers"/>
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
          <div class="session-row" v-for="session in filteredSessions" :key="session.id">
          <button
            class="session"
            :class="{ active: session.id === currentSessionId }"
            type="button"
            @click="activateSession(session.id)"
          >
            <span class="t">{{ session.title }}</span>
            <time>{{ session.time }}</time>
            <span class="s">{{ sessionPreview(session) }}</span>
          </button>
          <button class="session-delete icon-btn" type="button" :aria-label="`删除会话：${session.title}`" title="删除会话及数据库记录" :disabled="appStore.loading || queueRunning || deleting" @click="deleteTarget=session"><UiIcon name="delete" :size="14"/></button>
          </div>
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

    <div v-if="sessionsOpen && !sessionsDrawer" class="pane-resizer left-resizer" role="separator" aria-label="调整会话栏宽度" tabindex="0" @pointerdown="startResize($event,'left')" @keydown.left.prevent="resizePane('left',layoutWidths.sessions-20)" @keydown.right.prevent="resizePane('left',layoutWidths.sessions+20)"/>
    <main class="pane chat-col">
      <div class="pane-head">
        <h2>{{ currentSessionTitle }}</h2>
        <span class="spacer"></span>
        <span class="pill ok">{{ appStore.lastEngine || "LangGraph" }}</span>
        <ContextInspector ref="contextInspector" :thread-id="currentSessionId" :persona="appStore.currentPersona" :model-id="appStore.currentModelId" :active="appStore.loading||queueRunning"/>
      </div>
      <div class="pane-body" ref="threadScrollEl">
        <div ref="threadContentEl" class="thread">
          <article v-for="(item, index) in messages" :key="index" :class="['msg', item.role === 'user' ? 'user' : 'agent']">
            <div class="who">{{ item.kind==='compaction' ? '上下文压缩 · /compact' : item.role === "user" ? "你" : `${currentPersonaName} · ${item.model || "agent"}` }}</div>
            <div v-if="item.role==='user'" class="bubble">{{ item.content }}</div>
            <MarkdownMessage v-else class="bubble" :content="item.content"/>
            <div class="message-actions"><button type="button" title="复制消息" @click="copyMessage(item.content)"><UiIcon name="copy" :size="14"/>复制</button><button v-if="item.role === 'user'" type="button" :disabled="appStore.loading || shellPending || reverting" @click="revertConversation(index)"><UiIcon name="back" :size="14"/>回到此处</button></div>
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
          <ExecutionFeed v-if="appStore.loading || queueRunning" :thread-id="currentSessionId" :persona="appStore.currentPersona" :active="appStore.loading || queueRunning" :stopping="stopping" @run="executionId=$event"/>
        </div>
      </div>

      <div class="composer-wrap">
        <TaskPlan :thread-id="currentSessionId" :persona="appStore.currentPersona" :active="appStore.loading"/>
        <section v-if="pendingMessages.length" class="message-queue" aria-label="待发送消息"><header>等待回复 · {{pendingMessages.length}} 条</header><div v-for="(entry,index) in pendingMessages" :key="entry.id" class="queue-row"><span class="queue-index">{{index+1}}</span><button type="button" class="queue-text" @click="editQueued(entry.id)">{{entry.text}}</button><button type="button" class="icon-btn" aria-label="移除排队消息" @click="removeQueued(entry.id)"><UiIcon name="delete" :size="14"/></button></div></section>
        <div class="composer-surface">
          <section v-if="commandOpen" ref="commandPanel" class="slash-panel" role="dialog" aria-label="命令面板" @keydown="handleCommandKey">
            <div class="slash-search"><span aria-hidden="true">/</span><input ref="commandSearch" v-model="commandQuery" placeholder="搜索命令" aria-label="搜索命令" aria-controls="command-results"/><button type="button" class="icon-btn" aria-label="关闭命令面板" @click="commandOpen=false"><UiIcon name="close" :size="14"/></button></div>
            <div id="command-results" class="slash-results" role="listbox" aria-label="可用命令"><button v-for="(command,index) in filteredCommands" :id="`slash-command-${index}`" :key="command.name" :aria-label="`${command.name} · ${command.label}`" :aria-selected="index===commandIndex" :class="{selected:index===commandIndex}" type="button" role="option" :aria-disabled="commandDisabled(command)" :title="commandDisabled(command)?'请先创建会话或等待当前任务结束':command.description" @pointermove="commandIndex=index" @click="executeCommand(command.name)"><strong>{{command.name}}</strong><span>{{command.label}}<span class="slash-description"> · {{command.description}}</span></span><kbd v-if="index===commandIndex">↵</kbd></button><p v-if="!filteredCommands.length" class="slash-empty">没有匹配的命令</p></div>
            <footer class="slash-footer"><span>↑ ↓ 选择 <span>↵ 执行</span></span><span>Esc 关闭</span></footer>
          </section>
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
            <button v-if="(queueRunning || appStore.loading) && !composerText.trim()" class="send stop-button" type="button" aria-label="中止回复" title="中止回复" :disabled="stopping" @click="stopReply"><span class="stop-square"/></button>
            <button v-else class="send" type="submit" :aria-label="queueRunning?'加入队列':'发送'" :title="queueRunning?'加入队列，当前回复完成后发送':'发送'" :disabled="!composerText.trim() || reverting"><UiIcon name="arrowUp" :size="19"/></button>
          </div>
          <button v-if="shellMode" class="shell-indicator" type="button" @click="shellMode=false">Shell · 点击退出 / Esc</button>
          <Transition name="popover"><div v-if="composerText === '@'" class="composer-command-list"><button type="button" @click="insertComposer('请检索与当前任务相关的长期记忆：')">长期记忆</button><button type="button" @click="insertComposer('请使用已启用的技能分析以下问题：')">已启用技能</button></div></Transition>
        </form>
        </div>
        <p class="hint">
          {{ workModeHint }}
          <template v-if="appStore.lastActiveModel"> · 当前模型: {{ appStore.lastActiveModel }}</template>
        </p>
        <ToastNotice :message="interactionError || appStore.statusError"/>
      </div>
    </main>

    <div v-if="inspectorOpen && !inspectorDrawer" class="pane-resizer right-resizer" role="separator" aria-label="调整文件栏宽度" tabindex="0" @pointerdown="startResize($event,'right')" @keydown.left.prevent="resizePane('right',layoutWidths.inspector+20)" @keydown.right.prevent="resizePane('right',layoutWidths.inspector-20)"/>
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
  <ConfirmModal :visible="!!deleteTarget" title="删除此会话？" message="将删除此会话、对应数据库对话记录和任务计划，此操作无法撤销。" @cancel="deleteTarget=null" @confirm="deleteSession"/>
  <ConfirmModal :visible="clearConfirm" title="清空当前上下文？" message="清空后无法使用 /redo 恢复。" @cancel="clearConfirm=false" @confirm="clearContext"/>
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
import ExecutionFeed from '../components/ExecutionFeed.vue';
import MarkdownMessage from '../components/MarkdownMessage.vue';
import {request} from '../store/app';
import {useRouter} from 'vue-router';
import {useWorkbenchLayoutStore} from '../store/workbenchLayout';
import ConfirmModal from '../components/ConfirmModal.vue';
import ContextInspector from '../components/ContextInspector.vue';

type MessageItem = {
  kind?: string;
  id?: string;
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
const deleteTarget=ref<SessionItem|null>(null),deleting=ref(false);
let historyVersion=0;
async function deleteSession(){
  const target=deleteTarget.value;if(!target||deleting.value)return;
  deleting.value=true;
  try{
    const result=await request<{legacy_unresolved?:number}>('/api/workbench/session',{method:'DELETE',body:JSON.stringify({thread_id:target.id,persona:target.persona||appStore.currentPersona})});
    historyVersion++;
    pendingMessages.value=pendingMessages.value.filter(entry=>entry.thread!==target.id);
    sessions.value=sessions.value.filter(item=>item.id!==target.id);persistSessions();
    if(currentSessionId.value===target.id)newSession();
    deleteTarget.value=null;
    if(result.legacy_unresolved)interactionError.value=`会话已删除，有 ${result.legacy_unresolved} 条旧数据库记录无法唯一归属，请在对话记录页面核查`;
  }catch(e){interactionError.value=String(e);}finally{deleting.value=false;}
}
const currentSessionId = ref("");
const memoryVisible = ref(false);
const memoryInput = ref("");
const memorySaving = ref(false);
const memoryMessage = ref("");
const memoryError = ref(false);
const threadScrollEl = ref<HTMLElement | null>(null);
const threadContentEl=ref<HTMLElement|null>(null);
let threadObserver:ResizeObserver|undefined;
let followOutput=true;
function trackThreadScroll(){const el=threadScrollEl.value;if(el)followOutput=el.scrollHeight-el.clientHeight-el.scrollTop<80;}
onMounted(()=>{
  threadScrollEl.value?.addEventListener('scroll',trackThreadScroll,{passive:true});
  threadObserver=new ResizeObserver(()=>{if(followOutput)scrollToBottom();});
  if(threadContentEl.value)threadObserver.observe(threadContentEl.value);
});
onUnmounted(()=>{threadObserver?.disconnect();threadScrollEl.value?.removeEventListener('scroll',trackThreadScroll);});
const interactionError = ref('');
const shellPending=ref(false);
const router=useRouter(),shellMode=ref(false),commandOpen=ref(false),commandQuery=ref(''),turnDiff=ref('');
const layoutStore=useWorkbenchLayoutStore();
const {sessionsOpen,inspectorOpen}=storeToRefs(layoutStore);
sessionsOpen.value=window.innerWidth>=900&&localStorage.getItem('sc-sessions-open')!=='false';
inspectorOpen.value=window.innerWidth>=1180;
const workspaceEl=ref<HTMLElement|null>(null),workspaceWidth=ref(window.innerWidth);
function savedWidth(key:string,fallback:number,min:number,max:number){const value=Number(localStorage.getItem(key));return Number.isFinite(value)&&value>0?Math.max(min,Math.min(max,value)):fallback;}
const sessionWidth=ref(savedWidth('sc-session-width',254,190,420)),inspectorWidth=ref(savedWidth('sc-inspector-width',360,260,700));
const sessionsDrawer=computed(()=>workspaceWidth.value<900),inspectorDrawer=computed(()=>workspaceWidth.value<1180);
const drawerOpen=computed(()=>(sessionsDrawer.value&&sessionsOpen.value)||(inspectorDrawer.value&&inspectorOpen.value));
const layoutWidths=computed(()=>{
  const left=sessionsOpen.value&&!sessionsDrawer.value?sessionWidth.value:0;
  const right=inspectorOpen.value&&!inspectorDrawer.value?inspectorWidth.value:0;
  const budget=Math.max(0,workspaceWidth.value-20-560-(left?6:0)-(right?6:0));
  const minimum=(left?190:0)+(right?260:0),extra=Math.max(0,left+right-minimum);
  const scale=extra?Math.min(1,Math.max(0,budget-minimum)/extra):1;
  return {sessions:left?190+(left-190)*scale:sessionWidth.value,inspector:right?260+(right-260)*scale:inspectorWidth.value};
});
function closeDrawers(){if(sessionsDrawer.value)sessionsOpen.value=false;if(inspectorDrawer.value)inspectorOpen.value=false;}
watch(sessionsOpen,value=>{if(!sessionsDrawer.value)localStorage.setItem('sc-sessions-open',String(value));else if(value)inspectorOpen.value=false;});
watch(inspectorOpen,value=>{if(value&&sessionsDrawer.value)sessionsOpen.value=false;});
watch(sessionsDrawer,()=>{sessionsOpen.value=!sessionsDrawer.value&&localStorage.getItem('sc-sessions-open')!=='false';});
watch(inspectorDrawer,()=>{inspectorOpen.value=!inspectorDrawer.value;});
function resizePane(side:string,value:number){
  const other=side==='left'?(inspectorOpen.value&&!inspectorDrawer.value?layoutWidths.value.inspector+6:0):(sessionsOpen.value&&!sessionsDrawer.value?layoutWidths.value.sessions+6:0);
  const min=side==='left'?190:260,max=Math.min(side==='left'?420:700,workspaceWidth.value-20-560-6-other);
  const width=Math.max(min,Math.min(max,value));
  if(side==='left')sessionWidth.value=width;else inspectorWidth.value=width;
  localStorage.setItem(side==='left'?'sc-session-width':'sc-inspector-width',String(width));
}
let stopResize:(()=>void)|undefined;
function startResize(event:PointerEvent,side:string){event.preventDefault();stopResize?.();const target=event.currentTarget as HTMLElement;target.setPointerCapture(event.pointerId);const start=event.clientX,width=side==='left'?layoutWidths.value.sessions:layoutWidths.value.inspector;document.body.style.cursor='col-resize';document.body.style.userSelect='none';function move(e:PointerEvent){resizePane(side,width+(side==='left'?e.clientX-start:start-e.clientX));}function stop(){target.removeEventListener('pointermove',move);target.removeEventListener('pointerup',stop);target.removeEventListener('pointercancel',stop);document.body.style.cursor='';document.body.style.userSelect='';stopResize=undefined;}stopResize=stop;target.addEventListener('pointermove',move);target.addEventListener('pointerup',stop);target.addEventListener('pointercancel',stop);}
let workspaceObserver:ResizeObserver|undefined;
onMounted(()=>{workspaceObserver=new ResizeObserver(entries=>{workspaceWidth.value=entries[0].target.getBoundingClientRect().width;});if(workspaceEl.value)workspaceObserver.observe(workspaceEl.value);});
onUnmounted(()=>{workspaceObserver?.disconnect();stopResize?.();});
const contextInspector=ref<InstanceType<typeof ContextInspector>|null>(null),clearConfirm=ref(false);
const commandSearch=ref<HTMLInputElement|null>(null),commandIndex=ref(0),commandBusy=ref(false);
const commandPanel=ref<HTMLElement|null>(null);
const commands=[
  {name:'/new',label:'新会话',description:'开始独立对话',idle:true},
  {name:'/sessions',label:'查找会话',description:'打开会话栏并聚焦搜索'},
  {name:'/undo',label:'撤销上一轮',description:'回退到最近一条用户消息，保留为草稿',idle:true,session:true},
  {name:'/redo',label:'恢复回退',description:'恢复尚未被新消息替换的历史',idle:true,session:true},
  {name:'/compact',label:'压缩上下文',description:'调用当前模型生成摘要，保留原始记录',idle:true,session:true},
  {name:'/context',label:'查看上下文',description:'查看用量、摘要与原始消息'},
  {name:'/fork',label:'分叉会话',description:'复制当前可见历史到独立会话',idle:true,session:true},
  {name:'/export',label:'导出会话',description:'下载原始消息及上下文 JSON',session:true},
  {name:'/clear',label:'清空上下文',description:'确认后清空当前模型历史',idle:true,session:true},
  {name:'/models',label:'模型管理',description:'查看模型、提供商与模型组'},
  {name:'/mcp',label:'MCP 设置',description:'打开设置中的 MCP 管理'},
  {name:'/settings',label:'运行时设置',description:'管理技能、人格与权限'},
  {name:'/shell',label:'Shell 模式',description:'执行本机命令，受当前权限策略约束',idle:true},
  {name:'/files',label:'文件侧栏',description:'查看工作区文件与变更'},
  {name:'/help',label:'命令帮助',description:'打开命令面板'},
];
type WorkbenchCommand=typeof commands[number];
const filteredCommands=computed(()=>commands.filter(c=>(c.name+c.label+c.description).toLowerCase().includes(commandQuery.value.toLowerCase().trim().replace(/^\//,''))));
function commandDisabled(command:WorkbenchCommand){return commandBusy.value||!!(command.idle&&(appStore.loading||queueRunning.value||shellPending.value||reverting.value))||!!(command.session&&!currentSessionId.value);}
watch(commandQuery,()=>commandIndex.value=0);
watch(commandOpen,async value=>{if(value){commandQuery.value=composerText.value.startsWith('/')?composerText.value.slice(1):'';commandIndex.value=0;await nextTick();if(!composerText.value.startsWith('/'))commandSearch.value?.focus();}});
watch(composerText,value=>{if(/^\/\S*$/.test(value)){commandQuery.value=value.slice(1);commandOpen.value=true;}else if(document.activeElement===composerInput.value)commandOpen.value=false;});
function dismissCommands(event:PointerEvent){const target=event.target as Node;if(!commandPanel.value?.contains(target)&&!composerInput.value?.contains(target))commandOpen.value=false;}
onMounted(()=>document.addEventListener('pointerdown',dismissCommands));
onUnmounted(()=>document.removeEventListener('pointerdown',dismissCommands));
function handleCommandKey(event:KeyboardEvent){
  if(event.key==='Escape'){event.preventDefault();commandOpen.value=false;composerInput.value?.focus();return;}
  if(event.key==='ArrowDown'||event.key==='ArrowUp'){event.preventDefault();const count=filteredCommands.value.length;if(count)commandIndex.value=(commandIndex.value+(event.key==='ArrowDown'?1:-1)+count)%count;void nextTick(()=>commandPanel.value?.querySelector('.selected')?.scrollIntoView({block:'nearest'}));}
  if(event.key==='Enter'&&!event.isComposing){event.preventDefault();const command=filteredCommands.value[commandIndex.value];if(command&&!commandDisabled(command))void executeCommand(command.name);}
}
const modelOptions=computed(()=>appStore.models.filter(m=>m.enabled!==false&&!m.auxiliary_only).map(m=>({value:String(m.id),label:String(m.name||m.model||m.id),group:String(appStore.providers[String(m.provider)]?.name||m.provider||'提供商')})).sort((a,b)=>a.group.localeCompare(b.group)));
async function clearContext(){clearConfirm.value=false;try{await request('/api/workbench/session/reset',{method:'POST',body:JSON.stringify({thread_id:currentSessionId.value,persona:appStore.currentPersona})});messages.value=[];turnDiff.value='';updateSessionPreview();}catch(e){interactionError.value=String(e);}}
function updateSessionPreview(){const session=sessions.value.find(s=>s.id===currentSessionId.value);if(session)session.preview=JSON.stringify(messages.value);persistSessions();}
async function executeCommand(name:string){
  const command=commands.find(c=>c.name===name);if(!command)return;if(commandDisabled(command)){interactionError.value=command.session&&!currentSessionId.value?'请先发送消息创建会话':'请等待当前任务结束后使用此命令';return;}
  commandOpen.value=false;if(composerText.value.trim().startsWith('/'))composerText.value='';
  commandBusy.value=true;
  try{
    if(name==='/new')newSession();
    else if(name==='/clear')clearConfirm.value=true;
    else if(name==='/undo'){let index=messages.value.length-1;while(index>=0&&messages.value[index].role!=='user')index--;if(index>=0)await revertConversation(index);else interactionError.value='没有可撤销的用户消息';}
    else if(name==='/redo'){const data=await request<{messages:{id:string;role:string;content:string}[]}>('/api/workbench/session/unrevert',{method:'POST',body:JSON.stringify({thread_id:currentSessionId.value,persona:appStore.currentPersona})});messages.value=data.messages.map(m=>({id:m.id,role:m.role==='user'?'user':'agent',content:m.content}));turnDiff.value='';updateSessionPreview();}
    else if(name==='/fork'){const data=await request<{thread_id:string;messages:{id:string;role:string;content:string}[]}>('/api/workbench/session/fork',{method:'POST',body:JSON.stringify({thread_id:currentSessionId.value,persona:appStore.currentPersona})});const session=makeSession(currentSessionTitle.value+' · 分叉','[]');session.id=data.thread_id;sessions.value.unshift(session);currentSessionId.value=data.thread_id;historyVersion++;messages.value=data.messages.map(m=>({id:m.id,role:m.role==='user'?'user':'agent',content:m.content}));turnDiff.value='';updateSessionPreview();}
    else if(name==='/compact')await compactInConversation();
    else if(name==='/context')await contextInspector.value?.show();
    else if(name==='/export')await contextInspector.value?.exportSession();
    else if(name==='/models')await router.push('/models');
    else if(name==='/settings'||name==='/mcp')await router.push(name==='/mcp'?'/settings?tab=mcp':'/settings');
    else if(name==='/shell'){shellMode.value=true;await nextTick();composerInput.value?.focus();}
    else if(name==='/files')inspectorOpen.value=true;
    else if(name==='/sessions'){sessionsOpen.value=true;await nextTick();document.querySelector<HTMLInputElement>('.sessions input')?.focus();}
    else commandOpen.value=true;
  }catch(e){interactionError.value=String(e);}finally{commandBusy.value=false;}
}
async function compactInConversation(){
  if(reverting.value)return;
  const thread=currentSessionId.value,persona=appStore.currentPersona;
  reverting.value=true;
  const progress:MessageItem={id:crypto.randomUUID(),role:'agent',kind:'compaction',content:'正在压缩上下文…'};
  messages.value.push(progress);updateSessionPreview();scrollToBottom();
  try{
    await request('/api/workbench/context/compact',{method:'POST',body:JSON.stringify({thread_id:thread,persona,model_id:appStore.currentModelId||undefined})});
  }catch(e){progress.content=`上下文压缩失败：${String(e)}\n原始记录已保留，可以重试 /compact。`;interactionError.value=String(e);}
  finally{
    if(thread===currentSessionId.value&&persona===appStore.currentPersona)await loadSessionHistory(thread,persona);
    reverting.value=false;
  }
}
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
const currentPersonaName=computed(()=>personaOptions.value.find(p=>p.skill_id===appStore.currentPersona)?.name||appStore.currentPersona||'Agent');

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
  if(appStore.workMode==='sandbox')return '安全模式：可读取本地目录；写入限沙箱，外部代码执行禁用。Shift+Enter 换行。';
  return "对话模式：可读取本地目录与文件，不写入、不执行代码。Shift+Enter 换行。";
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
  if (appStore.loading || queueRunning.value || reverting.value) return;
  currentSessionId.value = "";
  historyVersion++;
  messages.value = [];
  composerText.value = "";
}

async function activateSession(id: string) {
  if (appStore.loading || queueRunning.value || reverting.value) return;
  if(sessionsDrawer.value)sessionsOpen.value=false;
  currentSessionId.value = id;
  const session = sessions.value.find((s) => s.id === id);
  if (session) {
    if(session.persona && session.persona !== appStore.currentPersona){appStore.currentPersona=session.persona;}
    await loadSessionHistory(id,session.persona||appStore.currentPersona);
  }
}
async function loadSessionHistory(id:string,persona:string){
  const version=++historyVersion;
  const session=sessions.value.find(s=>s.id===id);
  if(session){
    try { messages.value = JSON.parse(session.preview) as MessageItem[]; } catch { messages.value = []; }
    try {
      const data=await request<{messages:{id:string;role:string;content:string;kind?:string}[]}>('/api/workbench/session?'+new URLSearchParams({persona,thread_id:id}));
      if(version!==historyVersion||id!==currentSessionId.value||persona!==appStore.currentPersona)return;
      messages.value=data.messages.map(m=>({...m,id:m.id,role:m.role==='user'?'user':'agent',content:m.content}));
      session.preview=JSON.stringify(messages.value);persistSessions();
    } catch(e){interactionError.value=String(e);}
  }
}

function scrollToBottom() {
  void nextTick(() => {
    if (threadScrollEl.value) {
      threadScrollEl.value.scrollTop = threadScrollEl.value.scrollHeight;
    }
  });
}

const reverting = ref(false);
async function revertConversation(index:number) {
  if(reverting.value || appStore.loading || shellPending.value || !currentSessionId.value)return;
  reverting.value=true;interactionError.value='';
  try {
    const target=messages.value[index];
    if(!target.id){await activateSession(currentSessionId.value);interactionError.value='已重新加载服务器会话，请点击对应消息回退';return;}
    const data=await request<{draft:string;messages:{id:string;role:string;content:string}[]}>('/api/workbench/session/revert',{method:'POST',body:JSON.stringify({thread_id:currentSessionId.value,persona:appStore.currentPersona,message_id:target.id})});
    composerText.value=data.draft;
    messages.value=data.messages.map(m=>({id:m.id,role:m.role==='user'?'user':'agent',content:m.content}));
    turnDiff.value='';
    const session=sessions.value.find(s=>s.id===currentSessionId.value);
    if(session)session.preview=JSON.stringify(messages.value);
    persistSessions();
    await nextTick();
    document.querySelector<HTMLTextAreaElement>('.composer textarea')?.focus();
  } catch(e) {interactionError.value=e instanceof Error?e.message:'回退失败';}
  finally {reverting.value=false;}
}

type QueuedMessage={id:string;text:string;thread:string;persona:string;model:string;group:string;effort:string};
const pendingMessages=ref<QueuedMessage[]>([]),queueRunning=ref(false);
const executionId=ref(''),stopping=ref(false),queuePaused=ref(false);
async function stopReply(){queuePaused.value=true;stopping.value=true;try{let id=executionId.value;if(!id){const data=await request<{run_id:string}>('/api/execution?'+new URLSearchParams({thread_id:currentSessionId.value,persona:appStore.currentPersona}));id=data.run_id;}await request('/api/execution/stop',{method:'POST',body:JSON.stringify({thread_id:currentSessionId.value,persona:appStore.currentPersona,run_id:id})});}catch(e){interactionError.value=String(e);}finally{stopping.value=false;}}
function removeQueued(id:string){pendingMessages.value=pendingMessages.value.filter(entry=>entry.id!==id);}
function editQueued(id:string){const entry=pendingMessages.value.find(e=>e.id===id);if(!entry)return;if(composerText.value.trim()){interactionError.value='请先发送或清空当前草稿';return;}composerText.value=entry.text;removeQueued(id);composerInput.value?.focus();}
async function sendMessage(){
  const text=composerText.value.trim();
  if(!text||reverting.value)return;
  if(shellMode.value||text.startsWith('!')||text.startsWith('/')){
    if(queueRunning.value||appStore.loading){interactionError.value='任务执行期间请排队发送普通消息，命令请在任务结束后使用';return;}
    await executeMessage();return;
  }
  if(!currentSessionId.value){const session=makeSession(text.slice(0,24),'[]');currentSessionId.value=session.id;sessions.value.unshift(session);}
  pendingMessages.value.push({id:crypto.randomUUID(),text,thread:currentSessionId.value,persona:appStore.currentPersona,model:appStore.currentModelId,group:appStore.currentModelGroup,effort:appStore.reasoningEffort});
  composerText.value='';
  if(queueRunning.value)return;
  queuePaused.value=false;
  queueRunning.value=true;
  try{while(pendingMessages.value.length&&!queuePaused.value){const entry=pendingMessages.value.shift()!;await executeMessage(entry);}}finally{queueRunning.value=false;}
}

async function executeMessage(queued?:QueuedMessage) {
  const text = queued?.text || composerText.value.trim();
  if (!text || appStore.loading || reverting.value) {
    return;
  }
  if(text.startsWith('/')){const name=text.split(/\s/)[0];if(commands.some(c=>c.name===name)){await executeCommand(name);}else{interactionError.value='未知命令，请使用 /help';commandOpen.value=true;}return;}
  if(shellMode.value||text.startsWith('!')){if(shellPending.value)return;if(!currentSessionId.value)currentSessionId.value=`shell_${Date.now()}`;shellPending.value=true;try{const command=text.startsWith('!')?text.slice(1).trim():text;const result=await request<{stdout:string;stderr:string;exit_code:number}>('/api/workbench/shell',{method:'POST',body:JSON.stringify({command,thread_id:currentSessionId.value,persona:appStore.currentPersona})});messages.value.push({role:'user',content:'$ '+command},{role:'agent',content:`Shell · exit ${result.exit_code}\n${result.stdout||''}${result.stderr||''}`});composerText.value='';}catch(e){interactionError.value=e instanceof Error?e.message:'Shell 执行失败';}finally{shellPending.value=false;}return;}
  messages.value.push({ role: "user", content: text });
  followOutput=true;
  if(!queued)composerText.value = "";
  scrollToBottom();
  const requestPersona = queued?.persona || appStore.currentPersona;
  const requestThread=queued?.thread||currentSessionId.value;
  try {
    if (!currentSessionId.value) {
      const session = makeSession(text.slice(0, 24), JSON.stringify(messages.value));
      currentSessionId.value = session.id;
      sessions.value.unshift(session);
    }
    const before=await request<{diff?:string}>('/api/workbench/changes').catch(()=>({diff:''}));
    const data = await appStore.chat(text, queued?.thread || currentSessionId.value, queued?{persona:queued.persona,model_id:queued.model,model_group:queued.group,reasoning_effort:queued.effort}:undefined);
    messages.value.push({
      role: "agent",
      content: data.reply || "（空回复）",
      trace: data.trace || [],
      model: data.active_model,
    });
    if(data.messages?.length){
      messages.value=data.messages.map((m,index)=>({id:m.id,role:m.role==='user'?'user':'agent',content:m.content,...(index===data.messages!.length-1?{trace:data.trace||[],model:data.active_model}:{})}));
    }
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
    scrollToBottom();
    void request<{diff?:string}>('/api/workbench/changes').then(after=>{if(currentSessionId.value===requestThread&&appStore.currentPersona===requestPersona)turnDiff.value=after.diff!==before.diff?after.diff||'变更已清除':'';}).catch(()=>{});
  } catch (error) {
    const err = error instanceof Error ? error.message : "发送失败";
    interactionError.value=err;
    queuePaused.value=true;
    const failedSession=sessions.value.find(s=>s.id===currentSessionId.value);
    if(failedSession){failedSession.preview=JSON.stringify(messages.value);persistSessions();}
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
  if(commandOpen.value&&['ArrowDown','ArrowUp','Enter'].includes(event.key)&&!event.shiftKey&&!event.isComposing){handleCommandKey(event);return;}
  if(event.key==='Escape'){commandOpen.value=false;addMenu.value=false;shellMode.value=false;return;}
  if(event.key==='/' && !composerText.value){event.preventDefault();commandOpen.value=true;commandQuery.value='';return;}
  if(event.key==='!' && !composerText.value){event.preventDefault();shellMode.value=true;return;}
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); void sendMessage(); }
}
function globalEscape(event:KeyboardEvent){if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='k'){event.preventDefault();commandOpen.value=!commandOpen.value;}if(event.key==='Escape'){commandOpen.value=false;addMenu.value=false;closeDrawers();}}
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
watch(()=>appStore.currentPersona,async(persona)=>{
  if(appStore.loading||queueRunning.value)return;
  const selected=sessions.value.find(s=>s.id===currentSessionId.value);
  if(selected?.persona===persona){await loadSessionHistory(selected.id,persona);return;}
  const previous=sessions.value.find(s=>s.persona===persona);
  if(previous){currentSessionId.value=previous.id;await loadSessionHistory(previous.id,persona);}else newSession();
});

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
.slash-panel{position:absolute;left:0;right:0;bottom:calc(100% + 8px);z-index:40;box-sizing:border-box;overflow:hidden;border:1px solid var(--border);border-radius:12px;background:var(--bg);color:var(--fg);box-shadow:0 12px 36px #00000012;}
.slash-search{display:flex;align-items:center;gap:8px;padding:10px 12px;border-bottom:1px solid var(--border);}.slash-search>span{font:14px var(--font-mono);color:var(--muted);}.slash-search input{flex:1;min-width:0;width:100%;border:0!important;outline:none!important;box-shadow:none!important;background:transparent!important;color:var(--fg);font:13px/22px inherit;padding:0!important;border-radius:0;}.slash-search .icon-btn{flex-shrink:0;}
.slash-results{max-height:min(280px,calc(100dvh - 360px));min-height:32px;overflow:auto;overscroll-behavior:contain;padding:5px;}.slash-results button{box-sizing:border-box;display:flex;align-items:center;gap:10px;width:100%;min-height:32px;padding:7px 9px;border:0;border-radius:6px;background:transparent;color:var(--fg);text-align:left;cursor:pointer;}.slash-results button.selected,.slash-results button:hover{background:var(--surface-2);}.slash-results button[aria-disabled=true]{color:var(--muted);}.slash-results strong{flex-shrink:0;font:12px/18px var(--font-mono);font-weight:500;}.slash-results button>span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px;color:var(--muted);}.slash-description{color:var(--muted);}.slash-results kbd{margin-left:auto;flex-shrink:0;font-size:11px;color:var(--muted);}.slash-empty{padding:10px;font-size:12px;color:var(--muted);}.slash-footer{display:flex;justify-content:space-between;gap:12px;border-top:1px solid var(--border);padding:7px 12px;font-size:10px;color:var(--muted);}.slash-footer>span>span{margin-left:12px;}@media(max-height:620px){.slash-results{max-height:120px;}.slash-footer{display:none;}}@media(max-width:480px){.slash-description{display:none;}.slash-results{max-height:min(220px,calc(100dvh - 320px));}}
.composer-surface{position:relative;min-width:0;width:100%;}
.session-row{position:relative;display:flex;align-items:center;min-width:0;}.session-row>.session{flex:1;min-width:0;padding-right:36px;}.session-delete{position:absolute;right:5px;opacity:0;}.session-row:hover .session-delete,.session-row:focus-within .session-delete{opacity:1;}@media(hover:none){.session-delete{opacity:1;}}
.composer-toolbar>.send{flex-shrink:0;background:var(--fg);color:var(--bg);border:1px solid var(--fg);transition:opacity 150ms ease,transform 150ms ease;}.composer-toolbar>.send:hover:not(:disabled){background:var(--fg);color:var(--bg);border-color:var(--fg);opacity:.85;}.composer-toolbar>.send:focus-visible{outline:2px solid var(--accent);outline-offset:3px;}.stop-square{display:block;width:11px;height:11px;border-radius:2px;background:currentColor;}
.message-queue{border:1px solid var(--border);border-radius:12px;background:var(--bg-raised);padding:8px 10px;margin-bottom:8px;max-height:180px;overflow:auto;}.message-queue header{font-size:11px;color:var(--muted);padding:4px 6px 8px;}.queue-row{display:flex;align-items:center;gap:8px;min-height:32px;}.queue-index{font-size:10px;color:var(--muted);width:16px;text-align:center;}.queue-text{flex:1;min-width:0;text-align:left;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px;padding:5px;border-radius:5px;}.queue-text:hover{background:var(--surface-2);}
.workspace.with-inspector{display:flex!important;flex-direction:row;align-items:stretch;flex-wrap:nowrap;overflow:hidden;box-sizing:border-box;width:100%;height:100%;gap:0;padding:10px;}
.workspace.with-inspector>.sessions{display:flex;flex:0 0 var(--session-width,254px);width:var(--session-width,254px);min-width:0;min-height:0;}
.workspace.with-inspector>.pane-resizer{flex:0 0 6px;width:6px;min-height:0;}
.workspace.with-inspector>.chat-col{flex:1 1 0%;min-width:0;min-height:0;width:0;height:100%;container-type:inline-size;--chat-width:1120px;--chat-gutter:clamp(14px,3cqi,40px);}
.workspace.with-inspector>:deep(.workspace-panel){flex:0 0 var(--inspector-width,360px);width:var(--inspector-width,360px);min-width:0;min-height:0;box-sizing:border-box;height:100%;}
.drawer-backdrop{position:absolute;inset:0;z-index:110;background:#0006;border:0;border-radius:0;backdrop-filter:blur(2px);}
.workspace.with-inspector.sessions-drawer>.sessions{position:absolute;display:flex;z-index:111;inset:10px auto 10px 10px;width:min(320px,calc(100% - 56px));height:auto;border:1px solid var(--border);border-radius:12px;box-shadow:var(--shadow);}
.workspace.with-inspector.inspector-drawer>:deep(.workspace-panel){position:absolute;display:block;z-index:111;inset:10px 10px 10px auto;width:min(400px,calc(100% - 56px));height:auto;box-shadow:var(--shadow);}
.chat-col>.pane-head{min-width:0;padding-inline:16px;}
.chat-col>.pane-head h2{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0;}
.chat-col>.pane-head>.icon-btn,.chat-col>.pane-head>.pill{flex-shrink:0;}
/* Own the layout locally: legacy global flex rules cannot collapse this control. */
.composer-wrap{flex:0 0 auto;padding:12px 24px 18px;min-width:0;}
.chat-col>.pane-body{flex:1 1 0%;min-height:0;overflow:auto;}
.chat-col .thread{display:flex;flex-direction:column;justify-content:flex-start;align-items:stretch;width:100%;max-width:var(--chat-width);margin:0 auto;padding:28px var(--chat-gutter);box-sizing:border-box;gap:26px;}
.chat-col .msg{display:flex;flex-direction:column;flex:0 0 auto;gap:5px;width:100%;margin:0;}
.chat-col .msg.user{align-items:flex-end;max-width:100%;}
.chat-col .msg.agent{align-items:flex-start;}
.chat-col .msg.user .bubble{max-width:78%;}
.chat-col .msg.agent .bubble{width:100%;max-width:100%;}
.chat-col .who{margin-bottom:4px!important;}
.chat-col .message-actions{margin-top:3px;}
.chat-col .composer-wrap{width:100%;max-width:var(--chat-width);align-self:center;box-sizing:border-box;padding:8px var(--chat-gutter) 16px;}
.composer-wrap :deep(.task-plan-list),.composer-wrap .message-queue{max-height:12dvh;overflow:auto;}
.chat-col .composer-wrap>.hint{white-space:normal;margin:8px 0 0;font-size:10px;}
.composer{display:grid!important;grid-template-columns:minmax(0,1fr)!important;grid-template-rows:auto auto;align-items:stretch!important;justify-items:stretch;gap:10px;width:100%;min-width:0;box-sizing:border-box;border:1px solid var(--border);border-radius:14px;padding:16px 12px 10px;max-height:240px;}
.composer>textarea{grid-row:1;grid-column:1;width:100%!important;min-width:0;max-width:100%;min-height:56px;height:64px;max-height:160px;box-sizing:border-box;flex:none!important;resize:none;border:0!important;padding:4px 9px;background:transparent!important;font:400 14px/1.65 var(--font-body);}
.composer-toolbar{grid-row:2;grid-column:1;display:flex!important;flex-direction:row!important;align-items:center;justify-content:flex-start;flex-wrap:wrap;width:100%;min-width:0;gap:3px;}
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
.composer-toolbar :deep(.composer-control){max-width:min(200px,26cqi);}
.composer-toolbar{position:relative;}
.composer-toolbar :deep(.composer-picker){position:static;}
.composer-toolbar :deep(.composer-popover){left:0;right:auto;}
.composer :deep(.composer-popover),.composer-command-list{min-width:0;max-width:min(280px,80cqi);}
@container(max-width:600px){.composer-toolbar :deep(.composer-control){max-width:130px;font-size:12px;padding-inline:6px;}.composer-toolbar :deep(.composer-control>svg:first-child){display:none;}.chat-col .msg.user .bubble{max-width:90%;}.chat-col .thread{padding-block:20px;}.composer{padding:10px 8px 8px;}.chat-col .composer-wrap>.hint{display:none;}}
@media(max-width:650px){.workspace.with-inspector{padding:6px;}.chat-col>.pane-head{padding-inline:10px;}.chat-col>.pane-head>.pill{display:none;}}
@media(max-height:600px){.chat-col>.pane-head{height:44px;}.composer>textarea{height:44px;min-height:40px;}.chat-col .composer-wrap{padding-bottom:8px;}.chat-col .composer-wrap>.hint{display:none;}}
</style>

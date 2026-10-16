<template>
  <div class="app-shell">
    <header class="titlebar">
      <span class="mark" aria-hidden="true">雫</span>
      <span class="product">ShizukuAgent</span>
      <span class="crumb">{{ crumb }}</span>
      <span class="spacer"></span>
      <RouterLink class="top-link" to="/chat-sandbox">工作台</RouterLink>
      <RouterLink class="top-link" to="/models">模型</RouterLink>
      <RouterLink class="top-link" to="/settings">设置</RouterLink>
      <button class="theme-toggle" type="button" @click="appearance.toggle" :aria-label="appearance.theme === 'light' ? '切换深色主题' : '切换浅色主题'">
        <UiIcon :name="appearance.theme === 'light' ? 'moon' : 'sun'" :size="18"/>
      </button>
      <template v-if="isWorkbench">
        <button class="sidebar-toggle" type="button" title="隐藏或显示会话列表" aria-label="隐藏或显示会话列表" :aria-expanded="workbench.sessionsOpen" :aria-pressed="workbench.sessionsOpen" @click="workbench.toggleSessions"><UiIcon name="panelLeft" :size="17"/></button>
        <button class="sidebar-toggle" type="button" title="收起或展开右侧栏" aria-label="收起或展开右侧栏" :aria-expanded="workbench.inspectorOpen" :aria-pressed="workbench.inspectorOpen" @click="workbench.toggleInspector"><UiIcon name="panelRight" :size="17"/></button>
      </template>
    </header>
    <div class="management-shell" :class="{ 'is-workbench': isWorkbench }">
      <aside v-if="!isWorkbench" class="management-nav">
        <RouterLink class="back-link" to="/chat-sandbox"><UiIcon name="back"/> 返回工作台</RouterLink>
        <p class="nav-caption">模型与连接</p>
        <RouterLink to="/models"><UiIcon name="models"/>提供商与模型组</RouterLink>
        <RouterLink to="/config-editor"><UiIcon name="sliders"/>模型配置与辅助 API</RouterLink>
        <p class="nav-caption">智能体运行时</p>
        <RouterLink to="/settings"><UiIcon name="mcp"/>技能、人格与 MCP</RouterLink>
        <RouterLink to="/extensions"><UiIcon name="bot"/>技能市场与本机智能体</RouterLink>
        <RouterLink to="/security-init"><UiIcon name="security"/>安全与权限</RouterLink>
        <RouterLink to="/db-management"><UiIcon name="database"/>对话记录与存储</RouterLink>
        <p class="nav-caption">系统</p>
        <RouterLink to="/monitoring"><UiIcon name="activity"/>用量与资源监控</RouterLink>
        <RouterLink to="/logs"><UiIcon name="logs"/>运行日志</RouterLink>
        <RouterLink to="/diagnosis"><UiIcon name="refresh"/>连接诊断</RouterLink>
         <RouterLink to="/adapter-console"><UiIcon name="gateway"/>连接网关</RouterLink>
      </aside>
      <main class="page-content" v-content-motion:page="route.path">
      <slot />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import { useAppearanceStore } from "../store/appearance";
import { vContentMotion } from '../directives/contentMotion';
import { useWorkbenchLayoutStore } from '../store/workbenchLayout';

const route = useRoute();
const appearance = useAppearanceStore();
const workbench = useWorkbenchLayoutStore();
const isWorkbench = computed(() => route.path === '/chat-sandbox' || route.path === '/');
const crumb = computed(() => String(route.meta.title || "工作台"));
</script>

<style scoped>
.management-shell.is-workbench{min-width:0;overflow:hidden;}
.is-workbench>.page-content{min-width:0;overflow:hidden;}
.titlebar{min-width:0;}
.sidebar-toggle{display:grid;place-items:center;width:32px;height:32px;flex:0 0 32px;border:0;border-radius:7px;color:var(--muted);background:transparent;}
.sidebar-toggle:hover,.sidebar-toggle[aria-pressed=true]{background:var(--surface-2);color:var(--fg);}
.sidebar-toggle:focus-visible{outline:2px solid var(--accent);outline-offset:2px;}
.titlebar .mark,.titlebar .theme-toggle,.titlebar .top-link{flex-shrink:0;}
@media(max-width:480px){.titlebar{gap:4px;padding-inline:8px;}.titlebar .product{display:none;}.titlebar .top-link{padding:6px;font-size:12px;}}
@media(max-width:360px){.titlebar .product{display:none;}}
</style>

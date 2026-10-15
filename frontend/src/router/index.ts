import { createRouter, createWebHistory } from "vue-router";

const ChatSandboxPage = () => import("../pages/ChatSandboxPage.vue");
const ModelsPage = () => import("../pages/ModelsPage.vue");
const SettingsPage = () => import("../pages/SettingsPage.vue");
const ConfigEditorPage = () => import("../pages/ConfigEditorPage.vue");
const LogsPage = () => import("../pages/LogsPage.vue");
const MonitoringPage = () => import("../pages/MonitoringPage.vue");
const DbManagementPage = () => import("../pages/DbManagementPage.vue");
const DiagnosisPage = () => import("../pages/DiagnosisPage.vue");
const AdapterConsolePage = () => import("../pages/AdapterConsolePage.vue");
const AdapterLogsPage = () => import("../pages/AdapterLogsPage.vue");
const SecurityInitPage = () => import("../pages/SecurityInitPage.vue");

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {path:'/providers/:id',component:()=>import('../pages/ProviderEditorPage.vue'),meta:{title:'编辑提供商'}},
    { path: '/extensions', component: () => import('../pages/ExtensionsPage.vue'), meta: {title: '扩展与本机智能体'} },
    {
      path: "/",
      redirect: "/chat-sandbox",
    },
    {
      path: "/chat-sandbox",
      name: "chat-sandbox",
      component: ChatSandboxPage,
      meta: { title: "工作台" },
    },
    {
      path: "/models",
      name: "models",
      component: ModelsPage,
      meta: { title: "模型与模型组" },
    },
    {
      path: "/settings",
      name: "settings",
      component: SettingsPage,
      meta: { title: "设置" },
    },
    {
      path: "/config-editor",
      name: "config-editor",
      component: ConfigEditorPage,
      meta: { title: "配置编辑" },
    },
    {
      path: "/logs",
      name: "logs",
      component: LogsPage,
      meta: { title: "日志" },
    },
    {
      path: "/monitoring",
      name: "monitoring",
      component: MonitoringPage,
      meta: { title: "监控" },
    },
    {
      path: "/db-management",
      name: "db-management",
      component: DbManagementPage,
      meta: { title: "数据库" },
    },
    {
      path: "/diagnosis",
      name: "diagnosis",
      component: DiagnosisPage,
      meta: { title: "诊断" },
    },
    {
      path: "/adapter-console",
      name: "adapter-console",
      component: AdapterConsolePage,
      meta: { title: "连接网关" },
    },
    {
      path: "/adapter-logs",
      name: "adapter-logs",
      component: AdapterLogsPage,
      meta: { title: "网关日志" },
    },
    {
      path: "/security-init",
      name: "security-init",
      component: SecurityInitPage,
      meta: { title: "安全初始化" },
    },
  ],
});

export default router;

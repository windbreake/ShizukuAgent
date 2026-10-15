import { defineStore } from "pinia";
import { useDialogStore } from './dialog';
import { modelLabel } from '../modelIdentity';

const API_BASE = import.meta.env.VITE_API_BASE || "";

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    ...init,
  });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();
  if (!response.ok) {
    const message =
      typeof payload === "object" && payload && "error" in payload
        ? String((payload as { error?: string }).error)
        : typeof payload === 'object' && payload && 'detail' in payload
          ? String(payload.detail) : `HTTP ${response.status}`;
    throw new Error(message);
  }
  if (typeof payload === 'object' && payload?.success === false) throw new Error(payload.error || payload.message || '操作失败');
  return payload as T;
}

export type Persona = {
  filename?: string;
  skill_id?: string;
  name?: string;
  description?: string;
};

export type ModelGroup = {
  name?: string;
  purpose?: string;
  strategy?: string;
  models?: string[];
};

export type SkillItem = {
  skill_id?: string;
  name?: string;
  description?: string;
  enabled?: boolean;
  policy?: { enabled?: boolean; allow_model_invocation?: boolean };
};

export type McpServer = {
  id?: string;
  name?: string;
  description?: string;
  type?: string;
  enabled?: boolean;
  status?: string;
  tools?: string[];
  command?: string;
  args?: string[];
  url?: string;
};

export type ChatResponse = {
  messages?: {id:string;role:string;content:string}[];
  success: boolean;
  persona: string;
  reply: string;
  memory?: unknown[];
  engine?: string;
  trace?: Array<{ tool?: string; ok?: boolean; result?: string; args?: unknown }>;
  active_model?: string;
  error?: string;
};

export type ToastItem = {
  id: number;
  text: string;
  type: "success" | "error" | "info";
};

export const useAppStore = defineStore("app", {
  state: () => ({
    apiBase: API_BASE || "/",
    counter: 0,
    personas: [] as Persona[],
    currentPersona: localStorage.getItem('sc-persona') || "",
    modelGroups: {} as Record<string, ModelGroup>,
    currentModelGroup: "default",
    currentModelId: localStorage.getItem('sc-model-id') || "",
    reasoningEffort: localStorage.getItem('sc-reasoning-effort') || "default",
    workMode: "chat",
    models: [] as Array<Record<string, unknown>>,
    providers: {} as Record<string, Record<string, unknown>>,
    skills: [] as SkillItem[],
    mcpServers: [] as McpServer[],
    workModeEnabled: false,
    workModeScope: "global",
    loading: false,
    lastReply: "",
    lastTrace: [] as ChatResponse["trace"],
    lastEngine: "",
    lastActiveModel: "",
    memoryText: "",
    memoryMeta: null as Record<string, unknown> | null,
    statusError: "",
    toasts: [] as ToastItem[],
    toastSeq: 1,
  }),
  actions: {
    increment() {
      this.counter += 1;
    },
    async loadStatus() {
      try {
        const data = await request<{
          personas?: Persona[];
          default_persona?: string;
        }>("/api/agent/status");
        this.personas = (data.personas || []).map(p => ({...p, skill_id: p.skill_id || (p.filename || '').replace(/\.json$/,'' )})).filter((p,i,all)=>p.skill_id && all.findIndex(x=>x.skill_id===p.skill_id)===i);
        if (data.default_persona && !this.personas.some(p=>p.skill_id===this.currentPersona)) {
          this.currentPersona = data.default_persona;
        }
        const groups = await request<{
          default?: string;
          groups?: Record<string, ModelGroup>;
        }>("/api/model-groups");
        this.modelGroups = groups.groups || {};
        this.currentModelGroup =
          groups.default || Object.keys(this.modelGroups)[0] || "default";
        const models = await request<{
          success?: boolean;
          models?: Array<Record<string, unknown>> | Record<string, Record<string, unknown>>;
          providers?: Record<string, Record<string, unknown>>;
        }>("/api/models");
        this.models = Array.isArray(models.models) ? models.models : Object.entries(models.models || {}).map(([id, value]) => ({id, ...value}));
        this.models = this.models.map(model => ({...model,name:modelLabel(model)}));
        this.providers = models.providers || {};
        if (!this.models.some(m=>m.id===this.currentModelId && m.enabled!==false && !m.auxiliary_only)) this.currentModelId = String(this.models.find(m=>m.enabled !== false && !m.auxiliary_only)?.id || '');
        const skills = await request<{ success?: boolean; data?: SkillItem[] }>(
          "/api/systems/skills",
        );
        this.skills = skills.data || [];
        const mcp = await request<{ success?: boolean; data?: McpServer[] }>(
          "/api/systems/mcp",
        );
        this.mcpServers = mcp.data || [];
        await this.loadWorkMode();
      } catch (error) {
        this.statusError = error instanceof Error ? error.message : "加载状态失败";
      }
    },
    async loadWorkMode() {
      const data = await request<{
        success?: boolean;
        enabled?: boolean;
        global_enabled?: boolean;
        sandbox_enabled?: boolean;
      }>("/api/work_mode/status");
      this.workModeEnabled = Boolean(data.enabled || data.global_enabled);
      this.workMode = this.workModeEnabled ? 'full' : data.sandbox_enabled ? 'sandbox' : 'chat';
    },
    async toggleWorkMode(enable: boolean, scope = "global") {
      return this.setWorkMode(scope === 'sandbox' && enable ? 'sandbox' : enable ? 'full' : 'chat');
    },
    async setWorkMode(mode: string) {
      if (mode === this.workMode) return;
      const password = mode === 'full' ? await useDialogStore().password('开启完全控制', '验证安全密码后允许文件与 Shell 操作。') : '';
      if (password === null) return;
      const data = await request<{ success?: boolean; enabled?: boolean }>(
        "/api/work_mode/toggle",
        {
          method: "POST",
          body: JSON.stringify({ mode, password }),
        },
      );
      this.workMode = mode;
      this.workModeEnabled = mode === 'full';
      return data;
    },
    async chat(message: string, threadId?: string, options?:{persona:string;model_id:string;model_group:string;reasoning_effort:string}) {
      this.loading = true;
      try {
        const data = await request<ChatResponse>("/api/chat", {
          method: "POST",
          body: JSON.stringify({
            message,
            persona: this.currentPersona,
            model_group: this.currentModelGroup,
            model_id: this.currentModelId || undefined,
            reasoning_effort: this.reasoningEffort,
            thread_id: threadId,
            ...options,
          }),
        });
        this.lastReply = data.reply;
        this.lastTrace = data.trace || [];
        this.lastEngine = data.engine || "";
        this.lastActiveModel = data.active_model || "";
        return data;
      } finally {
        this.loading = false;
      }
    },
    async loadMemory() {
      const data = await request<{
        success: boolean;
        long_term?: string;
        meta?: Record<string, unknown>;
        error?: string;
      }>(`/api/agent/memory/long_term?include_meta=1&persona=${encodeURIComponent(this.currentPersona)}`);
      this.memoryText = String(data.long_term || "").trim();
      this.memoryMeta = data.meta ?? null;
      return data;
    },
    async addMemory(content: string) {
      return request<{ success: boolean; id?: number; error?: string }>(
        "/api/agent/memory",
        {
          method: "POST",
          body: JSON.stringify({ content, persona: this.currentPersona }),
        },
      );
    },
  },
});

import { defineStore } from 'pinia';

export const useWorkbenchLayoutStore = defineStore('workbench-layout', {
  state: () => ({ sessionsOpen: false, inspectorOpen: false }),
  actions: {
    toggleSessions() { this.sessionsOpen = !this.sessionsOpen; },
    toggleInspector() { this.inspectorOpen = !this.inspectorOpen; },
  },
});

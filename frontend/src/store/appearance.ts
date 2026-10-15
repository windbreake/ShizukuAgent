import { defineStore } from "pinia";
import { ref, watch } from "vue";

export const useAppearanceStore = defineStore("appearance", () => {
  const saved = localStorage.getItem("shizuku-theme");
  const theme = ref(saved === "dark" || saved === "light" ? saved : "light");
  watch(theme, (value) => {
    document.documentElement.dataset.theme = value;
    localStorage.setItem("shizuku-theme", value);
  }, { immediate: true });
  function toggle() { theme.value = theme.value === "light" ? "dark" : "light"; }
  return { theme, toggle };
});

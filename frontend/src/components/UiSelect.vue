<template>
  <div class="ui-select" ref="root" @keydown.esc="open=false">
    <button type="button" class="ui-select-trigger" :aria-label="label" :aria-expanded="open" @click="open=!open"><span class="ui-select-label">{{options.find(o=>o.value===modelValue)?.label || placeholder}}</span><ChevronDown :size="15"/></button>
    <Transition name="popover"><div v-if="open" class="ui-select-menu" role="listbox" :aria-label="label"><button v-for="option in options" :key="option.value" type="button" role="option" :aria-selected="option.value===modelValue" @click="emit('update:modelValue',option.value);open=false">{{option.label}}<Check v-if="option.value===modelValue" :size="14"/></button></div></Transition>
  </div>
</template>
<script setup lang="ts">
import {ref,onMounted,onUnmounted} from 'vue';import {ChevronDown,Check} from 'lucide-vue-next';
withDefaults(defineProps<{modelValue:string;options:{value:string;label:string}[];label?:string;placeholder?:string}>(),{label:'选择选项',placeholder:'请选择'});
const emit=defineEmits<{(e:'update:modelValue',value:string):void}>(),open=ref(false),root=ref<HTMLElement|null>(null);
function outside(e:PointerEvent){if(!root.value?.contains(e.target as Node))open.value=false;}
onMounted(()=>document.addEventListener('pointerdown',outside));onUnmounted(()=>document.removeEventListener('pointerdown',outside));
</script>
<style scoped>
.ui-select-label{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}.ui-select-trigger{min-width:0;}.ui-select-menu{min-width:160px;max-width:calc(100vw - 48px);}.ui-select-menu button{white-space:nowrap;}
.ui-select{position:relative;min-width:0}.ui-select-trigger{display:flex;align-items:center;justify-content:space-between;gap:12px;width:100%;height:38px;padding:0 12px;border:1px solid var(--border);border-radius:9px;background:var(--bg);color:var(--fg);font-size:13px;text-align:left}.ui-select-trigger:hover,.ui-select-trigger[aria-expanded=true]{border-color:var(--accent)}.ui-select-menu{position:absolute;top:calc(100% + 5px);left:0;right:0;z-index:150;padding:5px;max-height:250px;overflow:auto;border:1px solid var(--border);border-radius:10px;background:var(--surface);box-shadow:0 10px 30px #0002}.ui-select-menu button{display:flex;align-items:center;justify-content:space-between;gap:8px;width:100%;padding:10px;border:0;border-radius:7px;background:transparent;color:var(--fg);text-align:left;font-size:13px}.ui-select-menu button:hover,.ui-select-menu button[aria-selected=true]{background:var(--surface-2)}svg{flex-shrink:0}
</style>

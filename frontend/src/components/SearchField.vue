<template>
  <label class="search-field">
    <Search :size="16" aria-hidden="true"/>
    <input :value="modelValue" type="search" :placeholder="placeholder" :aria-label="placeholder" @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"/>
  </label>
</template>
<script setup lang="ts">
import {Search} from 'lucide-vue-next';
defineProps<{modelValue:string;placeholder:string}>();
const emit=defineEmits<{(e:'update:modelValue',value:string):void}>();
</script>
<style scoped>
.search-field{display:flex;align-items:center;gap:10px;width:100%;height:36px;padding:0 12px;box-sizing:border-box;background:var(--surface-2);border:1px solid transparent;border-radius:9px;color:var(--muted);transition:border-color 150ms;}
.search-field:focus-within{border-color:var(--accent);}
.search-field>input{flex:1;min-width:0;width:100%;height:100%;margin:0;padding:0!important;background:transparent!important;border:0!important;border-radius:0!important;box-shadow:none!important;outline:none;color:var(--fg);font:13px var(--font-body);appearance:none;}
.search-field>input::placeholder{color:var(--muted);opacity:1;}
.search-field>svg{flex-shrink:0;fill:none;}
</style>

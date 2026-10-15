<template>
  <div class="composer-picker" ref="root">
    <button type="button" class="composer-control" :aria-label="label" :aria-expanded="open" @click="open = !open"><UiIcon :name="label === '模型组' ? 'sparkles' : label === '人格' ? 'bot' : 'security'" :size="16"/><span>{{ selectedLabel }}</span><UiIcon name="chevron" :size="13"/></button>
    <Transition name="popover"><div v-if="open" class="composer-popover">
      <input v-model="query" :placeholder="`搜索${label}`" :aria-label="`搜索${label}`" @keydown.esc="open = false"/>
      <div class="picker-options"><template v-for="(option,index) in filtered" :key="option.value"><p v-if="option.group && (index === 0 || filtered[index-1].group !== option.group)" class="picker-group">{{option.group}}</p><button type="button" :class="{selected: option.value === modelValue}" @click="choose(option.value)">{{option.label}}<UiIcon v-if="option.value === modelValue" name="check" :size="16"/></button></template><p v-if="!filtered.length">没有匹配项</p></div>
      <RouterLink v-if="manage" :to="manage" @click="open = false"><UiIcon name="settings"/> 管理{{label}}</RouterLink>
    </div></Transition>
  </div>
</template>
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import UiIcon from './UiIcon.vue';
const props = defineProps<{modelValue:string;label:string;options:{value:string;label:string;group?:string}[];manage?:string}>();
const emit = defineEmits<{(e:'update:modelValue',value:string):void}>();
const open=ref(false),query=ref(''),root=ref<HTMLElement|null>(null);
const selectedLabel=computed(()=>props.options.find(o=>o.value===props.modelValue)?.label || props.label);
const filtered=computed(()=>props.options.filter(o=>o.label.toLowerCase().includes(query.value.toLowerCase())));
function choose(value:string){emit('update:modelValue',value);open.value=false;query.value='';}
function outside(event:PointerEvent){if(!root.value?.contains(event.target as Node))open.value=false;}
function escape(event:KeyboardEvent){if(event.key==='Escape')open.value=false;}
onMounted(()=>{document.addEventListener('pointerdown',outside);document.addEventListener('keydown',escape);});
onUnmounted(()=>{document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',escape);});
</script>
<style scoped>
.composer-picker{position:relative;display:block;min-width:0;flex:0 1 auto;}
.composer-control{display:flex;flex-direction:row;align-items:center;justify-content:flex-start;gap:7px;width:auto;max-width:230px;height:32px;min-height:32px;padding:5px 8px;border:0;border-radius:7px;box-shadow:none;background:transparent;color:var(--fg);font:400 13px/1.2 var(--font-body);cursor:pointer;}
.composer-control span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.composer-control:hover,.composer-control[aria-expanded=true]{background:var(--surface-2);}
.composer-control :deep(svg){width:16px;height:16px;fill:none;stroke:currentColor;flex-shrink:0;}
.composer-control :deep(svg:last-child){width:13px;height:13px;}
.composer-popover{position:absolute;bottom:calc(100% + 9px);left:0;z-index:100;width:280px;max-width:80vw;border:1px solid var(--border);border-radius:10px;background:var(--surface);box-shadow:0 8px 30px #0002;overflow:hidden;}
.composer-popover input{width:100%;box-sizing:border-box;border:0;border-bottom:1px solid var(--border);border-radius:0;padding:13px;font-size:13px;}
.picker-options{max-height:260px;overflow:auto;padding:4px;}
.picker-group{font-size:11px;color:var(--muted);padding:6px 12px;margin:0;}
.picker-options button{display:flex;flex-direction:row;justify-content:space-between;align-items:center;width:100%;padding:10px 12px;border:0;border-radius:6px;background:transparent;text-align:left;font-size:13px;}
.picker-options button:hover,.picker-options button.selected{background:var(--surface-2);}
.picker-options button.selected{color:var(--accent);}
.composer-popover>a{display:flex;align-items:center;gap:8px;padding:12px 14px;border-top:1px solid var(--border);font-size:12px;}
</style>

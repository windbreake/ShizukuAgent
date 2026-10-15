<template>
  <Teleport to="body"><dialog ref="panel" class="settings-dialog" :aria-label="title" @cancel.prevent="emit('close')" @click="onBackdrop">
    <header><h2>{{title}}</h2><button type="button" class="dialog-close" aria-label="关闭弹窗" @click="emit('close')"><X :size="16" :stroke-width="1.8"/></button></header>
    <div class="settings-dialog-body"><slot/></div>
  </dialog></Teleport>
</template>
<script setup lang="ts">
import {nextTick,onBeforeUnmount,ref,watch} from 'vue';
import {X} from 'lucide-vue-next';
const props=defineProps<{visible:boolean;title:string}>();
const emit=defineEmits<{(e:'close'):void}>();
const panel=ref<HTMLDialogElement|null>(null);
watch(()=>props.visible,async visible=>{await nextTick();if(visible&&!panel.value?.open)panel.value?.showModal();else if(!visible)panel.value?.close();},{immediate:true});
function onBackdrop(event:MouseEvent){if(event.target!==panel.value)return;const box=panel.value!.getBoundingClientRect();if(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom)emit('close');}
onBeforeUnmount(()=>panel.value?.close());
</script>
<style scoped>
.dialog-close{display:flex!important;align-items:center;justify-content:center;flex:0 0 28px;line-height:1;}.dialog-close>svg{display:block;flex:none;width:16px;height:16px;margin:0;}
.settings-dialog{position:fixed;inset:0;margin:auto;width:min(760px,calc(100vw - 40px));max-width:none;max-height:88dvh;padding:0;border:1px solid var(--border,#e7e9ed);border-radius:16px;background:var(--surface,#fff);color:var(--fg,#20242c);box-shadow:0 24px 80px #0004;box-sizing:border-box;overflow:auto;}.settings-dialog::backdrop{background:rgb(12 17 27 / .45);backdrop-filter:blur(4px);}.settings-dialog>header{position:sticky;top:0;z-index:1;display:flex;justify-content:space-between;align-items:center;gap:16px;padding:20px 24px;background:var(--surface,#fff);border-bottom:1px solid var(--border,#e7e9ed);}.settings-dialog h2{margin:0;font-size:17px;font-weight:600;}.dialog-close{display:grid;place-items:center;width:28px;height:28px;padding:0;border:0;border-radius:6px;background:var(--bg-raised,#f7f8fa);color:var(--muted,#828894);font-size:22px;cursor:pointer;}.settings-dialog-body{padding:22px 24px;}.settings-dialog-body:deep(form){display:grid;gap:14px;}.settings-dialog-body:deep(.field){display:grid;gap:7px;font-size:12px;}.settings-dialog-body:deep(input),.settings-dialog-body:deep(textarea),.settings-dialog-body:deep(select){width:100%;min-width:0;box-sizing:border-box;}.settings-dialog-body:deep(footer){display:flex;justify-content:flex-end;gap:8px;margin-top:8px;}@media(prefers-reduced-motion:no-preference){.settings-dialog[open]{animation:settings-dialog-in 180ms ease-out;}@keyframes settings-dialog-in{from{opacity:0;transform:translateY(6px) scale(.99)}to{opacity:1;transform:none}}}
</style>

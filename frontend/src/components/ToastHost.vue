<template><div ref="host" popover="manual" class="toast-host" aria-live="polite"><TransitionGroup name="toast"><div v-for="item in notices" :key="item.id" class="toast-message" :class="item.type" role="status"><CircleAlert v-if="item.type==='error'" :size="18"/><CircleCheck v-else :size="18"/><span>{{item.message}}</span><button type="button" aria-label="关闭提示" @click="dismiss(item.id)"><X :size="14"/></button></div></TransitionGroup></div></template>
<script setup lang="ts">
import {nextTick,ref,watch} from 'vue';
import {CircleAlert,CircleCheck,X} from 'lucide-vue-next';
import {notices,dismiss} from '../store/notifications';
const host=ref<HTMLElement|null>(null);
watch(notices,async()=>{await nextTick();if(notices.value.length){host.value?.hidePopover();host.value?.showPopover();}},{deep:true});
</script>
<style scoped>
.toast-host{position:fixed;inset:20px 20px auto auto;margin:0;padding:0;border:0;background:transparent;color:var(--fg);width:min(380px,calc(100vw - 40px));overflow:visible;pointer-events:none;}.toast-host:popover-open{display:grid;gap:10px;}.toast-message{display:flex;align-items:flex-start;gap:10px;padding:13px 14px;background:var(--surface,#fff);border:1px solid var(--border,#e7e9ed);border-radius:10px;box-shadow:0 8px 32px #0002;font-size:12px;line-height:1.6;pointer-events:auto;}.toast-message>svg{flex-shrink:0;margin-top:1px;color:var(--success);}.toast-message.error>svg{color:var(--danger);}.toast-message>span{flex:1;overflow-wrap:anywhere;}.toast-message button{display:grid;place-items:center;background:none;border:0;padding:3px;color:var(--muted);cursor:pointer;}.toast-enter-active,.toast-leave-active{transition:opacity 260ms ease,transform 260ms ease;}.toast-enter-from,.toast-leave-to{opacity:0;transform:translateY(-7px);}@media(prefers-reduced-motion:reduce){.toast-enter-active,.toast-leave-active{transition:opacity 150ms;}}
</style>

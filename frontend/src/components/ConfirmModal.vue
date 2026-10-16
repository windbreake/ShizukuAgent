<template>
  <Teleport to="body">
    <dialog ref="panel" class="confirm-dialog" aria-labelledby="confirm-title" aria-describedby="confirm-message" @cancel.prevent="emit('cancel')" @click="onBackdrop">
      <button class="confirm-close" type="button" aria-label="关闭弹窗" @click="emit('cancel')"><UiIcon name="close" :size="16"/></button>
      <div class="confirm-symbol"><UiIcon name="warning" :size="23"/></div>
      <h2 id="confirm-title">{{title}}</h2>
      <p id="confirm-message">{{message}}</p>
      <footer>
        <button ref="cancelButton" type="button" class="btn btn-ghost" @click="emit('cancel')">取消</button>
        <button type="button" class="btn btn-danger" @click="emit('confirm')">确认</button>
      </footer>
    </dialog>
  </Teleport>
</template>
<script setup lang="ts">
import {nextTick,onBeforeUnmount,ref,watch} from 'vue';
import UiIcon from './UiIcon.vue';
const props=defineProps<{visible:boolean;title:string;message:string}>();
const emit=defineEmits<{(e:'confirm'):void;(e:'cancel'):void}>();
const panel=ref<HTMLDialogElement|null>(null),cancelButton=ref<HTMLButtonElement|null>(null);
watch(()=>props.visible,async visible=>{await nextTick();if(visible){if(!panel.value?.open)panel.value?.showModal();cancelButton.value?.focus();}else panel.value?.close();},{immediate:true});
function onBackdrop(event:MouseEvent){if(event.target!==panel.value)return;const box=panel.value!.getBoundingClientRect();if(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom)emit('cancel');}
onBeforeUnmount(()=>panel.value?.close());
</script>
<style scoped>
.confirm-dialog{position:fixed;inset:0;margin:auto;width:min(440px,calc(100vw - 32px));max-width:none;max-height:calc(100dvh - 32px);box-sizing:border-box;overflow:auto;padding:26px;border:1px solid var(--border,#e7e9ed);border-radius:16px;background:var(--surface,#fff);color:var(--fg,#20242c);box-shadow:0 24px 80px #0004;}
.confirm-dialog::backdrop{background:rgb(12 17 27 / .45);backdrop-filter:blur(4px);}
.confirm-close{position:absolute;right:16px;top:16px;display:grid;place-items:center;width:28px;height:28px;padding:0;border:0;border-radius:7px;background:transparent;color:var(--muted);}
.confirm-close:hover{background:var(--surface-2);color:var(--fg);}
.confirm-symbol{display:grid;place-items:center;width:44px;height:44px;border-radius:12px;background:color-mix(in srgb,var(--danger,#dc4040) 12%,var(--surface,#fff));color:var(--danger,#dc4040);}
h2{margin:18px 0 8px;font-size:19px;line-height:1.4;font-weight:600;}
p{margin:0;font-size:13px;line-height:1.8;color:var(--muted);overflow-wrap:anywhere;}
footer{display:flex;justify-content:flex-end;gap:8px;margin-top:26px;}
@media(max-width:480px){.confirm-dialog{padding:22px;}}
</style>

<template>
  <Teleport to="body">
    <dialog ref="panel" class="mode-dialog" aria-labelledby="password-title" aria-describedby="password-description" @cancel.prevent="dialog.finish(null)" @click="onBackdrop">
      <form @submit.prevent="submit">
        <button class="dialog-close" type="button" aria-label="关闭弹窗" @click="dialog.finish(null)"><UiIcon name="close" :size="16"/></button>
        <div class="warning-symbol"><UiIcon name="warning" :size="23"/></div>
        <h2 id="password-title">{{dialog.title}}</h2>
        <p id="password-description">{{dialog.description}}</p>
        <label class="password-field" for="work-mode-password">安全密码</label>
        <input id="work-mode-password" ref="input" v-model="password" name="work-mode-password" type="password" autocomplete="off" required placeholder="输入安全密码"/>
        <RouterLink to="/security-init" class="dialog-help" @click="dialog.finish(null)">还未设置密码？前往权限设置</RouterLink>
        <footer><button class="btn btn-ghost" type="button" @click="dialog.finish(null)">取消</button><button class="btn btn-primary" type="submit" :disabled="!password">确认切换</button></footer>
      </form>
    </dialog>
  </Teleport>
</template>
<script setup lang="ts">
import {ref,watch,nextTick,onBeforeUnmount} from 'vue';
import {useDialogStore} from '../store/dialog';
import UiIcon from './UiIcon.vue';
const dialog=useDialogStore(),password=ref(''),input=ref<HTMLInputElement|null>(null),panel=ref<HTMLDialogElement|null>(null);
let previous:HTMLElement|null=null;
watch(()=>dialog.visible,async visible=>{
  password.value='';
  if(visible)previous=document.activeElement as HTMLElement;
  await nextTick();
  if(visible){if(!panel.value?.open)panel.value?.showModal();input.value?.focus();}
  else{panel.value?.close();if(previous?.isConnected)previous.focus();}
},{immediate:true});
function submit(){if(password.value)dialog.finish(password.value);}
function onBackdrop(event:MouseEvent){if(event.target!==panel.value)return;const box=panel.value!.getBoundingClientRect();if(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom)dialog.finish(null);}
onBeforeUnmount(()=>panel.value?.close());
</script>
<style scoped>
.mode-dialog{position:fixed;inset:0;margin:auto;width:min(440px,calc(100vw - 32px));max-width:none;max-height:calc(100dvh - 32px);box-sizing:border-box;overflow:auto;padding:26px;border:1px solid var(--border,#e7e9ed);border-radius:16px;background:var(--surface,#fff);color:var(--fg,#20242c);box-shadow:0 24px 80px #0004;}
.mode-dialog::backdrop{background:rgb(12 17 27 / .45);backdrop-filter:blur(4px);}
form{position:relative;display:flex;flex-direction:column;min-width:0;}
.dialog-close{position:absolute;right:-10px;top:-10px;display:grid;place-items:center;width:28px;height:28px;border:0;border-radius:7px;background:transparent;color:var(--muted);}
.dialog-close:hover{background:var(--surface-2);color:var(--fg);}
.warning-symbol{display:grid;place-items:center;width:44px;height:44px;border-radius:12px;background:color-mix(in srgb,#d99018 13%,var(--surface));color:#c18416;}
h2{margin:18px 0 8px;font-size:19px;line-height:1.4;font-weight:600;}
p{margin:0 0 22px;font-size:13px;color:var(--muted);line-height:1.7;overflow-wrap:anywhere;}
.password-field{display:block;margin-bottom:8px;font-size:12px;font-weight:500;}
input{display:block;box-sizing:border-box;width:100%;min-width:0;height:40px;padding:9px 12px;border:1px solid var(--border);border-radius:8px;background:var(--bg);color:var(--fg);font-size:14px;}
input:focus{outline:2px solid var(--accent);outline-offset:2px;}
.dialog-help{align-self:flex-start;margin-top:12px;font-size:12px;color:var(--muted);line-height:1.6;}
.dialog-help:hover{color:var(--accent);}
footer{display:flex;justify-content:flex-end;gap:8px;margin-top:24px;}
@media(max-width:480px){.mode-dialog{padding:22px;}}
</style>

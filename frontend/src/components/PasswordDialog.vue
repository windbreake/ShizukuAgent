<template>
  <Teleport to="body"><Transition name="dialog">
    <div v-if="dialog.visible" class="dialog-overlay" @click.self="dialog.finish(null)" @keydown.esc="dialog.finish(null)" @keydown.tab="trapFocus">
      <form ref="panel" class="app-dialog" role="dialog" aria-modal="true" aria-labelledby="password-title" @submit.prevent="submit">
        <div class="dialog-symbol"><UiIcon name="security" :size="22"/></div>
        <h2 id="password-title">{{dialog.title}}</h2><p>{{dialog.description}}</p>
        <label class="field">安全密码<input ref="input" v-model="password" type="password" autocomplete="current-password" required placeholder="输入安全密码"/></label>
        <RouterLink to="/settings" class="dialog-help" @click="dialog.finish(null)">还未设置密码？前往权限设置</RouterLink>
        <footer><button class="btn btn-ghost" type="button" @click="dialog.finish(null)">取消</button><button class="btn btn-primary" type="submit" :disabled="!password">确认切换</button></footer>
      </form>
    </div>
  </Transition></Teleport>
</template>
<script setup lang="ts">
import {ref,watch,nextTick} from 'vue';
import {useDialogStore} from '../store/dialog';
import UiIcon from './UiIcon.vue';
const dialog=useDialogStore(),password=ref(''),input=ref<HTMLInputElement|null>(null),panel=ref<HTMLElement|null>(null);
let previous:HTMLElement|null=null;
watch(()=>dialog.visible,async visible=>{password.value='';await nextTick();if(visible){previous=document.activeElement as HTMLElement;input.value?.focus();}else previous?.focus();});
function submit(){if(password.value)dialog.finish(password.value);}
function trapFocus(event:KeyboardEvent){const nodes=panel.value?.querySelectorAll<HTMLElement>('input,button,a');if(!nodes?.length)return;const first=nodes[0],last=nodes[nodes.length-1];if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}}
</script>

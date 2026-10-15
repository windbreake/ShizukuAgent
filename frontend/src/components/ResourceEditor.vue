<template>
  <Teleport to="body"><div v-if="resource" class="dialog-overlay" @keydown.esc="close">
    <form class="app-dialog resource-editor" role="dialog" aria-modal="true" aria-labelledby="resource-editor-title" @submit.prevent="save">
      <header><div><h2 id="resource-editor-title"><UiIcon name="edit"/>编辑源文件</h2><p>{{resource.key || 'MCP'}} / {{resource.filename}}</p></div><button class="icon-btn" type="button" aria-label="关闭编辑器" @click="close"><UiIcon name="back"/></button></header>
      <label class="field">文件内容<textarea ref="input" v-model="content" spellcheck="false" :disabled="loading" aria-label="文件内容"/></label>
      <p v-if="error" class="notice-error" role="alert">{{error}}</p>
      <footer><button type="button" class="btn" @click="close">取消</button><button class="btn btn-primary" :disabled="loading"><UiIcon name="save"/>{{loading?'处理中…':'保存文件'}}</button></footer>
    </form>
  </div></Teleport>
</template>
<script setup lang="ts">
import {ref,watch,nextTick} from 'vue';
import {request} from '../store/app';
const props=defineProps<{resource:{kind:string;key:string;filename:string}|null}>();
const emit=defineEmits<{(e:'close'):void;(e:'saved'):void}>();
const content=ref(''),original=ref(''),error=ref(''),loading=ref(false),input=ref<HTMLTextAreaElement|null>(null);
watch(()=>props.resource,async(resource)=>{if(!resource)return;error.value='';content.value='';original.value='';loading.value=true;try{const data=await request<{content:string}>('/api/settings-resources/document?'+new URLSearchParams(resource));content.value=data.content;original.value=data.content;}catch(e){error.value=String(e);}finally{loading.value=false;await nextTick();input.value?.focus();}});
function close(){if(content.value!==original.value&&!window.confirm('放弃尚未保存的文件修改？'))return;emit('close');}
async function save(){loading.value=true;error.value='';try{await request('/api/settings-resources/document',{method:'PUT',body:JSON.stringify({...props.resource,content:content.value})});emit('saved');emit('close');}catch(e){error.value=String(e);}finally{loading.value=false;}}
</script>
<style scoped>
.resource-editor{width:min(860px,94vw);display:flex;flex-direction:column;max-height:90dvh;}.resource-editor header{display:flex;align-items:start;justify-content:space-between;}.resource-editor h2{display:flex;align-items:center;gap:8px;}.resource-editor .field{display:grid;gap:8px;font-size:12px;min-height:0;}.resource-editor textarea{width:100%;height:50dvh;resize:vertical;font-family:var(--font-mono);font-size:12px;line-height:1.7;tab-size:2;white-space:pre;overflow:auto;}.resource-editor footer{display:flex;justify-content:flex-end;gap:8px;}
</style>

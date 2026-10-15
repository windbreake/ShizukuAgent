<template>
  <SettingsDialog :visible="Boolean(resource)" title="编辑源文件" @close="close">
    <form v-if="resource" class="resource-editor" @submit.prevent="save">
      <p>{{resource.key || 'MCP'}} / {{resource.filename}}</p>
      <label class="field">文件内容<textarea ref="input" v-model="content" spellcheck="false" :disabled="loading" aria-label="文件内容"/></label>
      <ToastNotice :message="error"/>
      <footer><button type="button" class="btn" @click="close">取消</button><button class="btn btn-primary" :disabled="loading || !loaded"><UiIcon name="save"/>{{loading?'处理中…':'保存文件'}}</button></footer>
    </form>
  </SettingsDialog>
</template>
<script setup lang="ts">
import {ref,watch,nextTick} from 'vue';
import {request} from '../store/app';
import SettingsDialog from './SettingsDialog.vue';
const props=defineProps<{resource:{kind:string;key:string;filename:string}|null}>();
const emit=defineEmits<{(e:'close'):void;(e:'saved'):void}>();
const content=ref(''),original=ref(''),error=ref(''),loading=ref(false),loaded=ref(false),input=ref<HTMLTextAreaElement|null>(null);
let generation=0;
watch(()=>props.resource,async(resource)=>{const version=++generation;loaded.value=false;if(!resource)return;error.value='';content.value='';original.value='';loading.value=true;try{const data=await request<{content:string}>('/api/settings-resources/document?'+new URLSearchParams(resource));if(version!==generation)return;content.value=data.content;original.value=data.content;loaded.value=true;}catch(e){if(version===generation)error.value=String(e);}finally{if(version===generation){loading.value=false;await nextTick();input.value?.focus();}}});
function close(){if(content.value!==original.value&&!window.confirm('放弃尚未保存的文件修改？'))return;emit('close');}
async function save(){if(!loaded.value||loading.value)return;loading.value=true;error.value='';try{await request('/api/settings-resources/document',{method:'PUT',body:JSON.stringify({...props.resource,content:content.value})});original.value=content.value;emit('saved');emit('close');}catch(e){error.value=String(e);}finally{loading.value=false;}}
</script>
<style scoped>
.resource-editor{min-width:0;}.resource-editor p{margin:0;color:var(--muted);font-size:12px;}.resource-editor textarea{height:48dvh;resize:vertical;font-family:var(--font-mono);font-size:12px;line-height:1.7;tab-size:2;white-space:pre;overflow:auto;}
</style>

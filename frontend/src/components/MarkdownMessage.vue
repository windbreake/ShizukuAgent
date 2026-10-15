<template><div class="markdown-message" v-html="html"/></template>
<script setup lang="ts">
import {computed} from 'vue';
import {marked} from 'marked';
import DOMPurify from 'dompurify';
const props=defineProps<{content:string}>();
const html=computed(()=>DOMPurify.sanitize(marked.parse(props.content,{async:false}) as string));
</script>
<style scoped>
.markdown-message{line-height:1.85;overflow-wrap:anywhere;white-space:normal;font-size:14px;}.markdown-message:deep(p){margin:0 0 12px;}.markdown-message:deep(pre){overflow:auto;max-height:480px;padding:16px;background:var(--code-bg);border:1px solid var(--border);border-radius:9px;white-space:pre;font:12px/1.7 var(--font-mono);}.markdown-message:deep(code){font-family:var(--font-mono);font-size:.9em;}.markdown-message:deep(a){color:var(--accent);text-decoration:underline;}.markdown-message:deep(table){display:block;overflow:auto;border-collapse:collapse;}.markdown-message:deep(td),.markdown-message:deep(th){border:1px solid var(--border);padding:7px 12px;}.markdown-message:deep(h1),.markdown-message:deep(h2),.markdown-message:deep(h3){font-size:1.15em;margin:20px 0 10px;}.markdown-message:deep(blockquote){margin-left:0;border-left:3px solid var(--border);padding-left:14px;color:var(--muted);}
</style>

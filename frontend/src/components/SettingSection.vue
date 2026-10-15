<template>
  <details class="setting-section" :open="open">
    <summary><UiIcon :name="icon"/><span>{{title}}</span><small v-if="count !== undefined">{{count}}</small><UiIcon name="chevron" class="fold-chevron"/></summary>
    <div class="setting-section-body"><slot/></div>
  </details>
</template>
<script setup lang="ts">
withDefaults(defineProps<{title:string;icon?:string;count?:number;open?:boolean}>(),{icon:'settings',open:true});
</script>
<style scoped>
.setting-section{border:1px solid var(--border);border-radius:12px;background:var(--surface);min-width:0;margin:0;overflow:clip;}.setting-section>summary{display:flex;align-items:center;gap:10px;padding:18px 20px;cursor:pointer;list-style:none;font-size:14px;font-weight:600;user-select:none;}.setting-section>summary::-webkit-details-marker{display:none;}.setting-section>summary:hover{background:var(--bg-raised);}.setting-section small{font-size:11px;color:var(--muted);font-weight:400;background:var(--surface-2);padding:2px 7px;border-radius:5px;}.fold-chevron{margin-left:auto;transition:transform 180ms ease;}.setting-section[open] .fold-chevron{transform:rotate(180deg);}.setting-section-body{padding:0 20px 20px;min-width:0;}.setting-section-body:deep(p){font-size:12px;color:var(--muted);line-height:1.7;}.setting-section-body:deep(form){display:grid;gap:12px;}.setting-section-body:deep(.field){display:grid;gap:7px;font-size:12px;}.setting-section-body:deep(input),.setting-section-body:deep(textarea),.setting-section-body:deep(select){width:100%;min-width:0;}.setting-section-body:deep(.setting-row){display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 0;border-bottom:1px solid var(--border);flex-wrap:wrap;}.setting-section-body:deep(.row-actions){display:flex;align-items:center;gap:8px;flex-wrap:wrap;}.setting-section-body:deep(.row-label){flex:1;min-width:130px;}.setting-section-body:deep(.row-label strong){font-size:13px;}.setting-section-body:deep(.row-label small){display:block;color:var(--muted);font-size:11px;margin-top:5px;overflow-wrap:anywhere;}@media(prefers-reduced-motion:reduce){.fold-chevron{transition:none;}}
</style>

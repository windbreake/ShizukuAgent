<template>
  <section class="db-page">
    <header><p class="kicker">设置 / 存储</p><h1><UiIcon name="database" :size="24"/>对话记录与存储</h1><p class="hint">按人格独立查看聊天记录，每页 20 条。</p></header>
    <div class="records-toolbar"><SearchField v-model="query" placeholder="搜索消息或角色"/><button class="btn" :disabled="loading" @click="refresh"><UiIcon name="refresh"/>刷新记录</button></div>
    <ToastNotice :message="error"/>
    <p v-if="!groups.length&&!loading" class="hint">暂无人格记录。</p>
    <details v-for="group in groups" :key="group.persona" class="persona-records" @toggle="onToggle(group.persona,$event)">
      <summary><UiIcon name="bot"/><strong>{{group.name}}</strong><span>{{group.total}} 条</span><UiIcon name="chevron"/></summary>
      <div class="persona-records-body">
        <p v-if="pages[group.persona]?.loading" class="hint">正在加载…</p>
        <template v-else>
          <article v-for="record in pages[group.persona]?.items||[]" :key="record.id" class="chat-record"><header><span class="record-role">{{record.role}}</span><time>{{record.created_at}}</time><button class="icon-btn" :aria-label="`删除记录 ${record.id}`" @click="deleting=record"><UiIcon name="delete" :size="14"/></button></header><p>{{record.content}}</p></article>
          <p v-if="!pages[group.persona]?.items.length" class="hint">暂无匹配记录。</p>
        </template>
        <footer class="record-pagination"><button class="btn" :disabled="!pages[group.persona]||pages[group.persona].page<=1||pages[group.persona].loading" @click="loadPage(group.persona,(pages[group.persona]?.page||1)-1)"><UiIcon name="back"/>上一页</button><span>{{pages[group.persona]?.page||1}} / {{Math.max(1,Math.ceil(group.total/20))}}</span><button class="btn" :disabled="(pages[group.persona]?.page||1)*20>=group.total||pages[group.persona]?.loading" @click="loadPage(group.persona,(pages[group.persona]?.page||1)+1)">下一页<UiIcon class="next-icon" name="back"/></button></footer>
      </div>
    </details>
    <ConfirmModal :visible="Boolean(deleting)" title="删除记录" :message="`确认删除记录 ${deleting?.id}？`" @cancel="deleting=null" @confirm="remove"/>
  </section>
</template>
<script setup lang="ts">
import {onMounted,onUnmounted,ref,reactive,watch} from 'vue';
import {request} from '../store/app';
import SearchField from '../components/SearchField.vue';
import ConfirmModal from '../components/ConfirmModal.vue';
type ChatRecord={id:number;persona:string;role:string;content:string;created_at:string};
type Page={items:ChatRecord[];page:number;loading:boolean};
const groups=ref<{persona:string;name:string;total:number}[]>([]),pages=reactive<Record<string,Page>>({}),query=ref(''),loading=ref(false),error=ref(''),deleting=ref<ChatRecord|null>(null);
const expanded=new Set<string>();let timer:ReturnType<typeof setTimeout>|undefined;let generation=0;
async function refresh(){const current=++generation;loading.value=true;error.value='';try{const [data,personas]=await Promise.all([request<{items:{persona:string;total:number}[]}>('/api/record-groups?query='+encodeURIComponent(query.value)),request<{personas:{filename:string;name:string}[]}>('/api/personas')]);if(current!==generation)return;const names=new Map((personas.personas||[]).map(p=>[p.filename.replace(/\.json$/,''),p.name]));const all=new Map((data.items||[]).map(item=>[item.persona,{...item,name:names.get(item.persona)||item.persona}]));for(const [persona,name] of names){if(!all.has(persona))all.set(persona,{persona,name,total:0});}groups.value=[...all.values()];for(const key of Object.keys(pages))delete pages[key];await Promise.all([...expanded].map(id=>loadPage(id,1)));}catch(e){error.value=String(e);}finally{if(current===generation)loading.value=false;}}
async function loadPage(persona:string,page:number){const current=generation;pages[persona]={items:[],page,loading:true};try{const data=await request<{items:ChatRecord[];page:number;total:number}>('/api/persona-records?'+new URLSearchParams({persona,page:String(page),query:query.value}));if(current!==generation)return;pages[persona]={items:data.items||[],page:data.page||1,loading:false};const group=groups.value.find(g=>g.persona===persona);if(group)group.total=data.total;}catch(e){if(current===generation){error.value=String(e);pages[persona].loading=false;}}}
function onToggle(persona:string,event:Event){if((event.target as HTMLDetailsElement).open){expanded.add(persona);if(!pages[persona])void loadPage(persona,1);}else expanded.delete(persona);}
async function remove(){const record=deleting.value;deleting.value=null;if(!record)return;try{await request('/api/delete_record',{method:'POST',body:JSON.stringify({id:record.id})});await loadPage(record.persona,pages[record.persona]?.page||1);}catch(e){error.value=String(e);}}
watch(query,()=>{clearTimeout(timer);timer=setTimeout(refresh,300);});
onMounted(refresh);onUnmounted(()=>clearTimeout(timer));
</script>
<style scoped>
.db-page{max-width:1080px!important;display:grid;gap:16px;}.db-page h1{display:flex;gap:10px;align-items:center;font-size:24px;}.records-toolbar{display:flex;gap:10px;align-items:center;}.records-toolbar>.search-field{flex:1;}.persona-records{border:1px solid var(--border);border-radius:12px;overflow:hidden;background:var(--surface);}.persona-records>summary{display:flex;align-items:center;gap:10px;padding:18px 20px;list-style:none;cursor:pointer;font-size:13px;}.persona-records>summary::-webkit-details-marker{display:none;}.persona-records>summary span{margin-left:auto;color:var(--muted);font-size:11px;}.persona-records[open]>summary{border-bottom:1px solid var(--border);}.persona-records[open]>summary>.ui-icon:last-child{transform:rotate(180deg);}.persona-records-body{padding:0 20px 16px;}.chat-record{padding:16px 0;border-bottom:1px solid var(--border);}.chat-record header{display:flex;align-items:center;gap:12px;color:var(--muted);font-size:11px;}.chat-record time{margin-left:auto;}.record-role{background:var(--bg-raised);padding:3px 7px;border-radius:5px;}.chat-record p{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;line-height:1.75;}.record-pagination{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:16px;}.record-pagination span{font-size:12px;color:var(--muted);}.next-icon{transform:rotate(180deg);}
</style>

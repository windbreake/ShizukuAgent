<template><component :is="icons[name] || CircleHelp" :size="size" :stroke-width="1.65" class="ui-icon" aria-hidden="true" /></template>
<script setup lang="ts">
import { ArrowUp, ArrowLeft, Plus, Search, ChevronDown, Check, Settings2, Moon, Sun, MessageSquare, Boxes, Plug, Brain, ShieldCheck, Puzzle, Volume2, Terminal, Activity, FileClock, Database, Cable, RefreshCw, Copy, Pencil, Trash2, Download, Save, CircleHelp, Sparkles, Bot, Folder, SlidersHorizontal, CircleCheck, Upload, PanelLeft, PanelRight, TriangleAlert, X } from 'lucide-vue-next';
withDefaults(defineProps<{name:string;size?:number}>(),{size:16});
const icons: Record<string,typeof Plus> = {panelLeft:PanelLeft,panelRight:PanelRight,warning:TriangleAlert,close:X,arrowUp:ArrowUp,back:ArrowLeft,plus:Plus,search:Search,chevron:ChevronDown,check:Check,settings:Settings2,moon:Moon,sun:Sun,chat:MessageSquare,models:Boxes,mcp:Plug,memory:Brain,security:ShieldCheck,skills:Sparkles,sparkles:Sparkles,plugins:Puzzle,voice:Volume2,terminal:Terminal,activity:Activity,logs:FileClock,database:Database,gateway:Cable,refresh:RefreshCw,copy:Copy,edit:Pencil,delete:Trash2,download:Download,save:Save,bot:Bot,folder:Folder,sliders:SlidersHorizontal,success:CircleCheck,upload:Upload};
</script>
<style scoped>.ui-icon{display:inline-block;flex:0 0 auto;vertical-align:middle;fill:none;}</style>

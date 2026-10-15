<template><span v-if="false"/></template>
<script setup lang="ts">
import {watch} from 'vue';
import {notify} from '../store/notifications';
const props=withDefaults(defineProps<{message?:string;type?:string}>(),{message:'',type:'error'});
watch(()=>[props.message,props.type],()=>notify(props.message,props.type),{immediate:true});
</script>

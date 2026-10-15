<template>
  <Teleport to="body">
    <Transition name="dialog">
      <div v-if="visible" class="dialog-overlay" @click.self="emit('cancel')" @keydown.esc="emit('cancel')">
        <div class="app-dialog" role="dialog" aria-modal="true" aria-labelledby="confirm-title" tabindex="-1" ref="panel">
          <div class="dialog-symbol danger"><UiIcon name="delete" :size="22"/></div>
          <h3 id="confirm-title" class="modal-title">{{ title }}</h3>
          <p class="modal-message">{{ message }}</p>
          <div class="modal-actions">
            <button type="button" class="btn btn-ghost" @click="emit('cancel')">取消</button>
            <button type="button" class="btn btn-danger" @click="emit('confirm')">确认</button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">

import {ref,watch,nextTick} from 'vue';
const props=defineProps<{ visible: boolean; title: string; message: string }>();
const panel=ref<HTMLElement|null>(null);
watch(()=>props.visible,async value=>{if(value){await nextTick();panel.value?.focus();}});
const emit = defineEmits<{ (e: "confirm"): void; (e: "cancel"): void }>();
</script>

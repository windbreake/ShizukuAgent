<template>
  <div class="collapse-section">
    <button type="button" class="collapse-toggle" @click="open = !open" :aria-expanded="open">
      <span>{{ title }}</span>
      <svg
        class="collapse-chevron"
        :class="{ open }"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <path d="M6 9l6 6 6-6" />
      </svg>
    </button>
    <Transition name="expand">
      <div v-if="open" class="collapse-body">
        <slot />
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";

defineProps<{ title: string }>();
const open = ref(false);
</script>
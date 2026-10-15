<template>
  <AppLayout>
    <router-view v-slot="{ Component, route }">
        <component :is="Component" :key="route.path" />
    </router-view>
  </AppLayout>
  <PasswordDialog />
</template>

<script setup lang="ts">
import AppLayout from "./layouts/AppLayout.vue";
import PasswordDialog from './components/PasswordDialog.vue';
</script>

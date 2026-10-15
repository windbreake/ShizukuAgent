<template>
  <AppLayout>
    <router-view v-slot="{ Component, route }">
        <component :is="Component" :key="route.path" />
    </router-view>
  </AppLayout>
  <PasswordDialog />
  <ToastHost />
</template>

<script setup lang="ts">
import AppLayout from "./layouts/AppLayout.vue";
import PasswordDialog from './components/PasswordDialog.vue';
import ToastHost from './components/ToastHost.vue';
</script>

<style>
button.switch[role="switch"]{appearance:none;position:relative;display:inline-block;box-sizing:border-box;width:24px!important;min-width:24px!important;height:16px!important;min-height:16px!important;flex:0 0 24px!important;padding:0!important;border-radius:4px!important;border:1px solid #c4c4c4;background:linear-gradient(180deg,#dedede,#e9e9e9);}
button.switch[role="switch"]::after{content:'';position:absolute;box-sizing:border-box;top:1px;left:1px;width:12px;height:12px;border-radius:3px!important;background:#fff;box-shadow:0 1px 2px #0003;transform:translateX(0);transition:transform 180ms ease;}
button.switch[role="switch"][aria-checked="true"]{background:linear-gradient(180deg,#5263f2,#6575ff);border-color:#4b5be0;}
button.switch[role="switch"][aria-checked="true"]::after{transform:translateX(8px);background:#fff;}
:root[data-theme="dark"] button.switch[role="switch"]:not([aria-checked="true"]){background:#41454f;border-color:#575c68;}
@media(prefers-reduced-motion:reduce){button.switch[role="switch"]::after{transition:none;}}
</style>

import { createApp } from "vue";
import { createPinia } from "pinia";

import App from "./App.vue";
import router from "./router";
import "./assets/styles.css";
import "./assets/modern.css";
import UiIcon from './components/UiIcon.vue';
import ToastNotice from './components/ToastNotice.vue';
import {useAppStore} from './store/app';

const app = createApp(App);

app.use(createPinia());
useAppStore().$subscribe((_mutation,state)=>{localStorage.setItem('sc-model-id',state.currentModelId);localStorage.setItem('sc-reasoning-effort',state.reasoningEffort);localStorage.setItem('sc-persona',state.currentPersona);},{detached:true});
app.use(router);
app.component('UiIcon', UiIcon);
app.component('ToastNotice', ToastNotice);
app.mount("#app");

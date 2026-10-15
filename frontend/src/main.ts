import { createApp } from "vue";
import { createPinia } from "pinia";

import App from "./App.vue";
import router from "./router";
import "./assets/styles.css";
import "./assets/modern.css";
import UiIcon from './components/UiIcon.vue';

const app = createApp(App);

app.use(createPinia());
app.use(router);
app.component('UiIcon', UiIcon);
app.mount("#app");

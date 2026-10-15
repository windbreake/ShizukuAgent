import { defineStore } from 'pinia';
import { ref } from 'vue';

export const useDialogStore = defineStore('dialog', () => {
  const visible = ref(false), title = ref(''), description = ref('');
  let resolve: ((value:string|null)=>void) | undefined;
  function password(nextTitle:string, nextDescription:string) {
    if (visible.value) finish(null);
    title.value=nextTitle;description.value=nextDescription;visible.value=true;
    return new Promise<string|null>(done=>{resolve=done;});
  }
  function finish(value:string|null) {visible.value=false;resolve?.(value);resolve=undefined;}
  return {visible,title,description,password,finish};
});

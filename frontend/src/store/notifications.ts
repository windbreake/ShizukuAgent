import {ref} from 'vue';
export const notices=ref<{id:number;message:string;type:string}[]>([]);
let nextId=0;
const recent=new Map<string,number>();
export function notify(message:string,type='error'){
  if(!message)return;
  const now=Date.now(),key=type+message;
  if(now-(recent.get(key)||0)<3500)return;
  recent.set(key,now);
  for(const [key,time] of recent)if(now-time>10000)recent.delete(key);
  const id=++nextId;
  notices.value=[...notices.value.slice(-2),{id,message,type}];
  setTimeout(()=>dismiss(id),3000);
}
export function dismiss(id:number){notices.value=notices.value.filter(item=>item.id!==id);}

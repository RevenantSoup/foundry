"use client";
import {useState,useEffect,useRef} from "react";
import {api,post} from "./client";
import type {Job} from "./types";
export function useJob(batch:string,onFinish:()=>Promise<void>){
 const [job,setJob]=useState<Job|null>(null);const [busy,setBusy]=useState(false);const [error,setError]=useState("");
 const finish=useRef(onFinish);const history=useRef("");
 useEffect(()=>{finish.current=onFinish},[onFinish]);
 async function poll(initial:Job){
   const previous=history.current;
   setBusy(true);setJob({...initial,log:previous+initial.log});
   let current=initial;
   while(current.status==="queued"||current.status==="running"){
     await new Promise(resolve=>setTimeout(resolve,650));
     current=await api<Job>("jobs/"+current.id);setJob({...current,log:previous+current.log});
   }
   history.current=previous+"\n["+current.action+" · exit "+current.exit_code+"]\n"+current.log+"\n";
   sessionStorage.removeItem("foundry-job:"+batch);
   await finish.current();
   if(current.status==="failed")setError("CLI exited "+current.exit_code+". "+current.log);
   setBusy(false);
   return current.status==="succeeded";
 }
 useEffect(()=>{
   const id=sessionStorage.getItem("foundry-job:"+batch);
   if(id)api<Job>("jobs/"+id).then(poll).catch(e=>{setError(e.message);setBusy(false)});
   // A durable server-side job is resumed once per batch mount.
   // eslint-disable-next-line react-hooks/exhaustive-deps
 },[batch]);
 async function run(action:string,payload:object={}){
   setError("");setBusy(true);
   try {const next=await post<Job>("batches/"+batch+"/actions",{action,...payload});
    sessionStorage.setItem("foundry-job:"+batch,next.id);return await poll(next);
   } catch(e){setError((e as Error).message);setBusy(false);return false}
 }
 return {run,job,busy,error};
}

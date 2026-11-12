"use client";
import {useState,useEffect,useRef} from "react";
import {api,post} from "./client";
import type {Job} from "./types";
export function useJob(batch:string,onFinish:()=>Promise<void>){
 const [job,setJob]=useState<Job|null>(null);const [busy,setBusy]=useState(false);const [error,setError]=useState("");
 const finish=useRef(onFinish);const history=useRef("");const generation=useRef(0);
 useEffect(()=>{finish.current=onFinish},[onFinish]);
 async function poll(initial:Job){
   const token=generation.current;
   const previous=history.current;
   setBusy(true);setJob({...initial,log:previous+initial.log});
   let current=initial;
   while(current.status==="queued"||current.status==="running"){
     await new Promise(resolve=>setTimeout(resolve,650));
     if(token!==generation.current)return false;
     current=await api<Job>("jobs/"+current.id);
     if(token!==generation.current)return false;
     setJob({...current,log:previous+current.log});
   }
   if(token!==generation.current)return false;
   history.current=previous+"\n["+current.action+" · exit "+current.exit_code+"]\n"+current.log+"\n";
   // An older component or tab must never erase a newer stage's resume pointer.
   if(sessionStorage.getItem("foundry-job:"+batch)===current.id)sessionStorage.removeItem("foundry-job:"+batch);
   await finish.current();
   if(token!==generation.current)return false;
   if(current.status==="failed")setError("CLI exited "+current.exit_code+". "+current.log);
   setBusy(false);
   return current.status==="succeeded";
 }
 useEffect(()=>{
   let active=true;
   const id=sessionStorage.getItem("foundry-job:"+batch);
   if(id)api<Job>("jobs/"+id).then(job=>active?poll(job):false).catch(e=>{if(active){setError(e.message);setBusy(false)}});
   return()=>{active=false;generation.current+=1};
   // Reconnect once per batch mount; leave the server worker running on unmount.
   // eslint-disable-next-line react-hooks/exhaustive-deps
 },[batch]);
 async function run(action:string,payload:object={}){
   setError("");setBusy(true);
   const token=generation.current;
   try {const next=await post<Job>("batches/"+batch+"/actions",{action,...payload});
    sessionStorage.setItem("foundry-job:"+batch,next.id);
    if(token!==generation.current)return false;
    return await poll(next);
   } catch(e){if(token===generation.current){setError((e as Error).message);setBusy(false)}return false}
 }
 return {run,job,busy,error};
}

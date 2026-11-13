"use client";
import {useCallback,useEffect,useRef,useState} from "react";
const unavailable="Workspace unavailable. Foundry cannot reach its dataset worker or database right now. The hosted Python worker may not be configured. Retry after the backend is available.";
export async function requestJSON<T>(url:string,options:RequestInit={},timeoutMs=10000):Promise<T>{
 const controller=new AbortController();let timedOut=false;
 const abort=()=>controller.abort();
 if(options.signal?.aborted)controller.abort();else options.signal?.addEventListener("abort",abort,{once:true});
 const timer=setTimeout(()=>{timedOut=true;controller.abort()},timeoutMs);
 try{
  const response=await fetch(url,{cache:"no-store",...options,signal:controller.signal});
  let body:Record<string,unknown>;
  try{body=await response.json()}catch{if(controller.signal.aborted)throw new Error("aborted");throw new Error("The server returned an invalid response. Please retry.")}
  if(!body||typeof body!=="object"||Array.isArray(body)||!Object.keys(body).length)throw new Error("The server returned an invalid response. Please retry.");
  if(!response.ok||body.error){
   if(body.error==="database_unavailable"||/Python bridge unavailable|dataset store.{0,20}unavailable|Worker.{0,20}(unavailable|unreachable)/i.test(String(body.message||body.error)))throw new Error(unavailable);
   throw new Error(typeof body.message==="string"?body.message:response.status===401?"Your session has expired. Sign in again.":"Request failed (HTTP "+response.status+"). Please retry.");
  }
  return body as T;
 }catch(error){
  if(timedOut)throw new Error("Request timed out. The backend did not respond within "+timeoutMs/1000+" seconds. Please retry.");
  if(controller.signal.aborted)throw new DOMException("Request cancelled","AbortError");
  if(error instanceof TypeError)throw new Error("Cannot connect to Foundry. Check your connection and retry.");
  throw error;
 }finally{clearTimeout(timer);options.signal?.removeEventListener("abort",abort)}
}
export const api=<T>(url:string,options?:RequestInit)=>requestJSON<T>("/api/"+url,options,options?.method&&options.method!=="GET"?120000:10000);
export const post=<T>(url:string,body:object)=>api<T>(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
export function useRemote<T>(url:string|null,interval=5000){
 const [data,setData]=useState<T|null>(null);const [error,setError]=useState("");
 const read=useRef<()=>Promise<void>>(async()=>{});
 const refresh=useCallback(()=>read.current(),[]);
 useEffect(()=>{
  let active=true;let request:AbortController|null=null;let timer:ReturnType<typeof setTimeout>|undefined;
  async function load(){
   if(!url||!active)return;
   clearTimeout(timer);request?.abort();const current=new AbortController();request=current;
   setError("");
   try{const value=await api<T>(url,{signal:current.signal});if(active&&request===current){setData(value);setError("");timer=setTimeout(()=>{if(document.visibilityState==="visible")void load();else timer=setTimeout(()=>void load(),interval)},interval)}}
   catch(e){if(active&&request===current&&!current.signal.aborted)setError((e as Error).message)}
  }
  read.current=load;void Promise.resolve().then(()=>{if(active){setData(null);setError("");void load()}});
  return()=>{active=false;clearTimeout(timer);request?.abort();read.current=async()=>{}};
 },[url,interval]);
 return {data,error,refresh};
}
export function format(value:number){return value.toLocaleString("en-US")}
export function percent(value:number|null){return value===null?"—":(value*100).toFixed(1)+"%"}
export function asset(params:Record<string,string>){return "/api/asset?"+new URLSearchParams(params)}

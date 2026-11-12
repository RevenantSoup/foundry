"use client";
import {useCallback,useEffect,useState} from "react";
export async function api<T>(url:string,options?:RequestInit):Promise<T>{
 const response=await fetch("/api/"+url,{cache:"no-store",...options});
 const body=await response.json();
 if(!response.ok||body.error)throw new Error(body.error||"Request failed");
 return body;
}
export const post=<T>(url:string,body:object)=>api<T>(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
export function useRemote<T>(url:string,interval=5000){
 const [data,setData]=useState<T|null>(null);const [error,setError]=useState("");
 const refresh=useCallback(async()=>{try{setData(await api<T>(url));setError("")}catch(e){setError((e as Error).message)}},[url]);
 useEffect(()=>{let active=true;
 const read=async()=>{try{const value=await api<T>(url);if(active){setData(value);setError("")}}catch(e){if(active)setError((e as Error).message)}};
 void read();const timer=setInterval(()=>{if(document.visibilityState==="visible")void read()},interval);
 return()=>{active=false;clearInterval(timer)};
 },[url,interval]);
 return {data,error,refresh};
}
export function format(value:number){return value.toLocaleString("en-US")}
export function percent(value:number|null){return value===null?"—":(value*100).toFixed(1)+"%"}
export function asset(params:Record<string,string>){return "/api/asset?"+new URLSearchParams(params)}

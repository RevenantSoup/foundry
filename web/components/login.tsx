"use client";
import Link from "next/link";
import {useState,useSyncExternalStore} from "react";
import {useRouter,useSearchParams} from "next/navigation";
import {Button} from "./ui/button";
import {Field,FieldGroup,FieldLabel} from "./ui/field";
import {Input} from "./ui/input";
import {ErrorBox,PageHeader,Panel} from "./common";
const subscribe=()=>()=>{};
export function Login(){
 const hydrated=useSyncExternalStore(subscribe,()=>true,()=>false);
 const [error,setError]=useState("");const [busy,setBusy]=useState(false);const router=useRouter();const search=useSearchParams();
 async function submit(event:React.FormEvent<HTMLFormElement>){
  event.preventDefault();setError("");setBusy(true);
  const form=new FormData(event.currentTarget);
  try{
   const response=await fetch("/api/auth/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({user:form.get("user"),password:form.get("password")})});
   const result=await response.json();if(!response.ok)throw new Error(result.message||"Login failed");
   const next=search.get("next");router.replace(next?.startsWith("/")&&!next.startsWith("//")&&!next.includes("\\")?next:"/");router.refresh();
  }catch(error){setError((error as Error).message);setBusy(false)}
 }
 return <div className="login-layout"><PageHeader title="Welcome back." description="Sign in to the Foundry admin workspace. The marketplace stays public."/><Panel title="Admin sign in" description="One workspace. One admin credential."><form method="post" onSubmit={submit} className="login-form"><FieldGroup><Field><FieldLabel htmlFor="login-user">Username</FieldLabel><Input disabled={!hydrated} id="login-user" name="user" autoComplete="username" required maxLength={200}/></Field><Field><FieldLabel htmlFor="login-password">Password</FieldLabel><Input disabled={!hydrated} id="login-password" name="password" type="password" autoComplete="current-password" required maxLength={1000}/></Field></FieldGroup><ErrorBox message={error}/><Button type="submit" disabled={busy||!hydrated}>{busy?"Signing in…":"Sign in"}</Button><Link className="text-link" href="/datasets">Browse the public marketplace</Link></form></Panel></div>
}

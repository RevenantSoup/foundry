"use client";
import Link from "next/link";
import {useRef,useState} from "react";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {ErrorBox} from "./common";
import {requestJSON} from "@/lib/client";
export function CheckoutForm({dataset}:{dataset:string}){
 const [email,setEmail]=useState(""),[key,setKey]=useState(""),[error,setError]=useState(""),[busy,setBusy]=useState(false);
 const attempt=useRef("");
 async function submit(event:React.FormEvent){
  event.preventDefault();if(busy)return;setBusy(true);setError("");attempt.current||=crypto.randomUUID();
  try{
   const body=await requestJSON<{url:string}>("/api/v1/checkout",{method:"POST",headers:{"Content-Type":"application/json",Authorization:"Bearer "+key,"Idempotency-Key":attempt.current},body:JSON.stringify({dataset_id:dataset,email})});
   const url=new URL(body.url);if(url.protocol!=="https:"||url.hostname!=="checkout.stripe.com")throw new Error("Invalid checkout response.");
   window.location.assign(url.href);
  }catch(e){setError((e as Error).message);setBusy(false)}
 }
 return <form className="checkout-placeholder" onSubmit={submit}><h3>Stripe test checkout</h3><p>Test mode only. No real money. Enter card details only on Stripe’s hosted page.</p><label className="field-label" htmlFor="checkout-email">Buyer email</label><Input id="checkout-email" type="email" autoComplete="email" required value={email} onChange={e=>{setEmail(e.target.value);attempt.current=""}}/><label className="field-label mt-3" htmlFor="checkout-key">Buyer API key</label><Input id="checkout-key" type="password" autoComplete="off" required value={key} onChange={e=>{setKey(e.target.value);attempt.current=""}}/><p className="field-help">Your key stays in memory. You’ll enter it again after returning to retrieve the paid download.</p><ErrorBox message={error}/><Button className="mt-3 w-full" type="submit" disabled={busy}>{busy?"Opening checkout…":"Continue to Stripe test checkout"}</Button></form>
}
export function CheckoutReturn({order,cancelled=false}:{order?:string;cancelled?:boolean}){
 const [key,setKey]=useState(""),[error,setError]=useState(""),[status,setStatus]=useState(""),[download,setDownload]=useState("");
 async function check(event:React.FormEvent){event.preventDefault();setError("");setDownload("");try{const body=await requestJSON<{status:string;download_url?:string;expires_at:number}>("/api/v1/orders/"+encodeURIComponent(order||""),{headers:{Authorization:"Bearer "+key},cache:"no-store"});setStatus(body.status);if(body.download_url&&body.expires_at>Date.now()/1000)setDownload(body.download_url);else if(body.download_url)setError("The 24-hour download link has expired.")}catch(e){setError((e as Error).message)}}
 return <section className="empty-state"><h1>{cancelled?"Checkout cancelled":"Check your test order"}</h1><p>{cancelled?"No download has been granted. You can return to the marketplace and try again.":"A redirect is not proof of payment. Downloads appear only after a verified Stripe webhook and expire 24 hours after confirmation."}</p>{!cancelled&&order?<form onSubmit={check}><label className="field-label" htmlFor="receipt-key">Buyer API key</label><Input id="receipt-key" type="password" autoComplete="off" value={key} required onChange={e=>setKey(e.target.value)}/><Button className="mt-3" type="submit">Check payment status</Button><ErrorBox message={error}/>{status?<p role="status">Order status: {status}</p>:null}{download?<div className="button-row mt-3"><a className="text-link" href={download}>Download images + manifest ZIP</a><a className="text-link" href={download+"&kind=manifest"}>Download manifest CSV</a></div>:null}</form>:null}<Link className="text-link mt-5" href="/datasets">Return to marketplace</Link></section>
}

"use client";
import {useState} from "react";
import Link from "next/link";
import {CircleHelp,ArrowRight} from "lucide-react";
import {Button} from "./ui/button";
import {Dialog,DialogContent,DialogHeader,DialogTitle,DialogDescription,DialogFooter} from "./ui/dialog";
import {useRemote} from "@/lib/client";
import type {State} from "@/lib/types";
const storageKey="foundry-tour-v1-dismissed";
export function GuidedTour(){
 const [invitation,setInvitation]=useState(()=>{try{return localStorage.getItem(storageKey)!=="true"}catch{return true}});
 const [open,setOpen]=useState(false);const [step,setStep]=useState(0);
 const {data}=useRemote<State>(open?"state":null);
 const batch=data?.batches[0]?.id;
 const steps=[
  {title:"Your workspace at a glance",description:"The overview reads real batch counts, yield, rights and quota usage. Synthetic fixtures stay labeled.",href:"/"},
  {title:"Start a new dataset",description:"Describe one visible attribute and upload exactly six reference images. Review the plan before running harvest and filter.",href:"/new"},
  {title:"Inspect the batch",description:"Follow real stage counts, source failures, row licences, attribution and provenance. Resume interrupted work from its batch.",href:batch?"/batches/"+batch:"/batches"},
  {title:"Review before packaging",description:"Accept or reject all 200 sampled images. The CLI blocks packaging below 90% precision; the UI cannot bypass it.",href:batch?"/batches/"+batch+"/qa":"/batches"},
  {title:"Discover and share responsibly",description:"The public catalog lists cleared datasets. Review licence obligations and attribution. Checkout is an explicit no-payment placeholder.",href:"/datasets"},
 ];
 function dismiss(){setOpen(false);setInvitation(false);try{localStorage.setItem(storageKey,"true")}catch{}}
 return <><aside className="tour-invitation" aria-label="Guided tour">{invitation&&!open?<><span>New to Foundry?</span><Button size="sm" onClick={()=>{setStep(0);setOpen(true)}}>Take the tour</Button><Button variant="ghost" size="sm" onClick={dismiss}>Skip tour</Button></>:<Button variant="outline" size="sm" aria-label="Open guided tour" onClick={()=>{setStep(0);setOpen(true)}}><CircleHelp data-icon="inline-start"/>Tour</Button>}</aside><Dialog open={open} onOpenChange={value=>value?setOpen(true):dismiss()} modal={false}><DialogContent className="tour-dialog"><DialogHeader><span className="muted">{step+1} / {steps.length}</span><DialogTitle>{steps[step].title}</DialogTitle><DialogDescription>{steps[step].description}</DialogDescription></DialogHeader><Button variant="outline" render={<Link href={steps[step].href}/>} nativeButton={false}>Open this page <ArrowRight data-icon="inline-end"/></Button><DialogFooter><Button variant="ghost" onClick={dismiss}>Skip / close tour</Button><Button disabled={step===0} variant="outline" onClick={()=>setStep(step-1)}>Back</Button><Button onClick={()=>step===steps.length-1?dismiss():setStep(step+1)}>{step===steps.length-1?"Finish tour":"Next step"}</Button></DialogFooter></DialogContent></Dialog></>
}

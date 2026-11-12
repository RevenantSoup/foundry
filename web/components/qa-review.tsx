"use client";
/* eslint-disable @next/next/no-img-element */
import {useState} from "react";
import Link from "next/link";
import {Check,X,ArrowLeft,ArrowRight,ScanLine,ExternalLink} from "lucide-react";
import {Button} from "@/components/ui/button";
import {Progress} from "@/components/ui/progress";
import {PageHeader,Panel,ErrorBox,Loading,Fixture,JobLog} from "./common";
import {asset,percent,useRemote} from "@/lib/client";
import {useJob} from "@/lib/jobs";
import type {Detail} from "@/lib/types";
export function QAReviewPage({id}:{id:string}){
 const {data,error,refresh}=useRemote<Detail>("batches/"+id,2000);
 if(!data)return <><ErrorBox message={error}/><Loading/></>;
 return <><div className="breadcrumb"><Link href={"/batches/"+id}><ArrowLeft size={13} className="inline"/> Back to batch</Link></div><PageHeader title="A human check, on every sample." description={data.prompt} action={<Fixture synthetic={data.synthetic}/>}/><ReviewPanel detail={data} refresh={refresh}/></>
}
export function ReviewPanel({detail,refresh,onContinue}:{detail:Detail;refresh:()=>Promise<void>;onContinue?:()=>void}){
 const worker=useJob(detail.id,refresh);
 if(!detail.samples.length)return <Panel title="Prepare your review" description="The CLI selects 200 distinct images and creates labeled crops."><p className="muted">You need at least 200 accepted images after filtering. QA sampling is deterministic and persistent.</p><div className="button-row mt-5"><Button disabled={worker.busy} onClick={()=>worker.run("qa")}><ScanLine/>Generate contact sheet</Button></div><ErrorBox message={worker.error}/><JobLog job={worker.job}/></Panel>;
 return <ReviewGrid key={detail.id} detail={detail} refresh={refresh} onContinue={onContinue}/>
}
function ReviewGrid({detail,refresh,onContinue}:{detail:Detail;refresh:()=>Promise<void>;onContinue?:()=>void}){
 const [verdicts,setVerdicts]=useState<Record<string,string>>(()=>{const initial=Object.fromEntries(detail.samples.map(s=>[s.row_id,s.verdict]));try{return {...initial,...JSON.parse(localStorage.getItem("foundry-review:"+detail.id)||"{}")}}catch{return initial}});
 const [filter,setFilter]=useState("all");const worker=useJob(detail.id,refresh);
 const ids=detail.samples.map(s=>s.row_id);
 const accepted=ids.filter(id=>verdicts[id]==="accept").length;
 const rejected=ids.filter(id=>verdicts[id]==="reject").length;
 const reviewed=accepted+rejected;const precision=reviewed?accepted/reviewed:null;
 const complete=reviewed===200;const unchanged=ids.every(id=>(verdicts[id]||"")===(detail.samples.find(s=>s.row_id===id)?.verdict||""));const failing=ids.filter(id=>verdicts[id]==="reject");
 function choose(id:string,verdict:string){setVerdicts(current=>{const next={...current,[id]:verdict};localStorage.setItem("foundry-review:"+detail.id,JSON.stringify(next));return next})}
 const rowsById=new Map(detail.rows.map(row=>[row.id,row]));
 async function submit(){await worker.run("review",{verdicts:ids.map(id=>({id,verdict:verdicts[id]}))})}
 return <div className="review-workspace"><div className="review-summary"><div><span>REVIEW PROGRESS</span><strong>{reviewed}<small> / 200</small></strong><Progress value={reviewed/2}/></div><div><span>RUNNING PRECISION</span><strong className={precision!==null&&precision<.90?"negative":"lime"}>{percent(precision)}</strong><p>{accepted} accepted · {rejected} rejected</p></div><div><span>QUALITY GATE</span><strong>≥90<small>%</small></strong><p>All 200 verdicts required</p></div><div className="review-submit"><Button disabled={!complete||worker.busy} onClick={submit}>Submit 200 verdicts <ArrowRight data-icon="inline-end"/></Button><span>{complete?"Submit to validate with the CLI":"Review "+(200-reviewed)+" more images"}</span></div></div>
 {detail.synthetic?<div className="fixture-note">Synthetic fixture review · These patterned images test the workflow. They are not evidence of model precision.</div>:null}
 <ErrorBox message={worker.error}/><JobLog job={worker.job}/>
 {complete&&precision!==null&&precision<.90?<ErrorBox message={"Packaging blocked: precision "+percent(precision)+" is below 90%. Failing IDs: "+failing.join(", ")}/>:null}
 {detail.qa_passed&&unchanged?<div className="success-note"><Check size={17}/>Review recorded. CLI quality gate passed.<Button variant="outline" onClick={onContinue} render={onContinue?undefined:<Link href={"/new?batch="+detail.id}/>} nativeButton={!!onContinue}>Continue to package <ArrowRight/></Button></div>:null}
 <details className="contact-preview"><summary>View 200-image contact sheet <ExternalLink size={13} className="inline"/></summary><a href={asset({kind:"contact",batch:detail.id})} target="_blank" rel="noreferrer"><img src={asset({kind:"contact",batch:detail.id})} alt="Contact sheet of all 200 labeled QA samples"/></a></details>
 <div className="toolbar review-toolbar"><div className="button-row">{[["all","All 200"],["unreviewed","Unreviewed"],["accept","Accepted"],["reject","Rejected"]].map(([value,label])=><Button key={value} variant={filter===value?"default":"outline"} onClick={()=>setFilter(value)}>{label}</Button>)}</div><span className="muted">Click an image to toggle · drafts saved in this browser</span></div>
 <div className="crop-grid">{detail.samples.filter(s=>filter==="all"||(filter==="unreviewed"?!verdicts[s.row_id]:verdicts[s.row_id]===filter)).map((sample,index)=>{
 const id=sample.row_id;const row=rowsById.get(id);const verdict=verdicts[id];
 return <article className={"crop-card "+(verdict||"unreviewed")} key={id}><button className="crop-image-button" aria-label={"Toggle verdict for "+id} onClick={()=>choose(id,verdict==="accept"?"reject":"accept")}><img loading="lazy" src={asset({kind:"crop",batch:detail.id,id})} alt={"QA sample "+id}/><span className="crop-number">{String(sample.position+1).padStart(3,"0")}</span>{verdict?<span className="crop-verdict">{verdict==="accept"?<Check size={15}/>:<X size={15}/>}</span>:null}</button><div className="crop-info"><code title={id}>{id}</code><span className="crop-licence">{row?.licence}</span><span className="crop-attribution">{row?.attribution}</span></div><div className="crop-controls"><Button size="sm" variant={verdict==="accept"?"default":"ghost"} aria-label={"Accept image "+id} onClick={()=>choose(id,"accept")}><Check/>Accept</Button><Button size="sm" variant={verdict==="reject"?"destructive":"ghost"} aria-label={"Reject image "+id} onClick={()=>choose(id,"reject")}><X/>Reject</Button></div><span className="sr-only">Sample {index+1}: {verdict||"unreviewed"}</span></article>
 })}</div></div>
}

"use client";
import Link from "next/link";
import {Skeleton} from "./ui/skeleton";
import {ArrowUpRight,LoaderCircle,TriangleAlert} from "lucide-react";
import {Badge} from "@/components/ui/badge";
import {Button} from "@/components/ui/button";
import {Card,CardContent,CardHeader,CardTitle,CardDescription} from "@/components/ui/card";
import type {Batch,Job} from "@/lib/types";
import {format,percent} from "@/lib/client";
export function PageHeader({title,description,action}:{title:string;description:string;action?:React.ReactNode}){return <header className="page-header"><div><h1>{title}</h1><p>{description}</p></div>{action}</header>}
export function Panel({title,description,children,className=""}:{title:string;description?:string;children:React.ReactNode;className?:string}){return <Card className={"panel "+className}><CardHeader><CardTitle role="heading" aria-level={2}>{title}</CardTitle>{description?<CardDescription>{description}</CardDescription>:null}</CardHeader><CardContent>{children}</CardContent></Card>}
export function ErrorBox({message,retry}:{message:string;retry?:()=>Promise<void>}){return message?<div className="error-box" role="alert"><TriangleAlert size={18}/><span>{message}</span>{retry?<Button variant="outline" onClick={()=>void retry()}>Retry</Button>:null}</div>:null}
export function RemoteStatus({error,retry}:{error:string;retry:()=>Promise<void>}){return error?<div><ErrorBox message={error}/><Button variant="outline" onClick={()=>void retry()}>Retry</Button></div>:<Loading/>}
export function Loading(){return <div aria-busy="true" aria-label="Loading workspace"><div className="loading"><LoaderCircle className="spin" size={24}/> Reading your workspace…</div><div className="stats-grid">{[0,1,2].map(n=><Skeleton className="h-24" key={n}/>)}</div></div>}
export function Empty({title,description}:{title:string;description:string}){return <div className="empty-state"><LayersMark/><h3>{title}</h3><p>{description}</p><Button render={<Link href="/new"/>} nativeButton={false}>Create a dataset <ArrowUpRight data-icon="inline-end"/></Button></div>}
function LayersMark(){return <span className="empty-mark">◇</span>}
export function Status({batch}:{batch:Batch}){return <Badge variant={batch.status==="Packaged"||batch.qa_passed?"default":"secondary"}>{batch.status}</Badge>}
export function Fixture({synthetic}:{synthetic:boolean}){return synthetic?<Badge variant="outline" className="fixture">Synthetic fixture</Badge>:<Badge variant="outline">Live sources</Badge>}
export function BatchList({batches}:{batches:Batch[]}){return batches.length?<div className="table-scroll"><table className="data-table"><thead><tr><th>Dataset / batch</th><th>Status</th><th>Sources & licences</th><th>Harvested</th><th>QA precision</th><th></th></tr></thead><tbody>{batches.map(b=><tr key={b.id}><td><Link href={"/batches/"+b.id} className="row-link">{b.prompt}</Link><div className="subline"><code>{b.id.slice(0,10)}</code><Fixture synthetic={b.synthetic}/></div></td><td><Status batch={b}/></td><td><div>{b.sources.join(", ")||"Pending harvest"}</div><div className="subline rights">{b.licences.join(" · ")||"Rights checked on harvest"}</div></td><td className="numeric">{format(b.harvested)}</td><td className="numeric">{percent(b.qa_precision)}</td><td><Link href={"/batches/"+b.id} aria-label={"Open "+b.prompt}><ArrowUpRight size={18}/></Link></td></tr>)}</tbody></table></div>:<Empty title="Your next dataset starts here" description="Write one image specification and add six references. Foundry takes it from there."/>}
export function JobLog({job}:{job:Job|null}){if(!job)return null;return <div className="job-log" aria-live="polite"><div><strong>{job.action} · {job.status}</strong><span>{job.exit_code!==undefined?"Exit "+job.exit_code:"Working…"}</span></div><pre>{job.log||"Starting the Python CLI…"}</pre></div>}

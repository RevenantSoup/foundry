"use client";
import Link from "next/link";
import {Plus,Layers3,ImageIcon,ListFilter,PackageCheck,ScanLine,ArrowUpRight,ArrowDownRight,Database} from "lucide-react";
import {Button} from "@/components/ui/button";
import {Progress} from "@/components/ui/progress";
import {PageHeader,Panel,BatchList,ErrorBox,Loading} from "./common";
import {Funnel,MixChart,BatchHistory,Distribution,QuotaHistory} from "./charts";
import {format,percent,useRemote} from "@/lib/client";
import type {State} from "@/lib/types";
export function Overview(){
 const {data,error}=useRemote<State>("state");
 if(!data)return <><ErrorBox message={error}/><Loading/></>;
 const today=new Date().toISOString().slice(0,10);
 const used=data.quota.find(q=>q.day===today&&q.source==="youtube")?.units||0;
 const stats=[{label:"Total batches",value:format(data.totals.batches),icon:Layers3,note:"Across your workspace"},{label:"Harvested frames",value:format(data.totals.harvested),icon:ImageIcon,note:"Deduplicated at source"},{label:"Shortlisted",value:format(data.totals.shortlisted),icon:ListFilter,note:"Passed to verification"},{label:"Packaged rows",value:format(data.totals.packaged),icon:PackageCheck,note:"Ready to download"},{label:"Avg. QA precision",value:percent(data.totals.precision),icon:ScanLine,note:"Across reviewed batches"}];
 return <><PageHeader title="Your data, refined." description="From image specifications to traceable datasets." action={<Button size="lg" render={<Link href="/new"/>} nativeButton={false}><Plus data-icon="inline-start"/>New dataset</Button>}/><ErrorBox message={error}/>
 <section className="stats-grid">{stats.map(({label,value,icon:Icon,note})=><div className="stat" key={label}><div className="stat-label"><Icon size={16}/>{label}</div><strong>{value}</strong><span>{note}</span></div>)}</section>
 <div className="section-heading"><span><i/> WORKSPACE ACTIVITY</span><span>Live from your local SQLite database</span></div>
 <div className="dashboard-charts"><Panel title="Yield pipeline" description="Fewer frames. A stronger dataset."><Funnel totals={data.totals}/><div className="panel-foot"><ArrowDownRight size={14}/>{data.totals.harvested?((data.totals.packaged/data.totals.harvested)*100).toFixed(1):0}% of harvested frames packaged</div></Panel><Panel title="Source mix" description="Where your harvested frames come from.">{data.sources.length?<MixChart data={data.sources}/>:<div className="empty-chart">Your sources will appear after harvest.</div>}</Panel></div>
 <Panel title="Recent batches" description="Your latest specifications and where they stand." className="recent-panel"><BatchList batches={data.batches.slice(0,5)}/>{data.batches.length>0?<Link className="text-link panel-link" href="/batches">View all batches <ArrowUpRight size={15}/></Link>:null}</Panel>
 <div className="two-column"><Panel title="Licence breakdown" description="Rights stay attached to every frame."><div className="licence-list">{["CC0","CC-BY","CC-BY-SA","platform_public_as_is"].map(name=>{const count=data.licences.find(x=>x.name===name)?.value||0;return <div key={name}><div><span>{name}</span><strong>{format(count)}</strong></div><Progress value={data.totals.harvested?count/data.totals.harvested*100:0}/></div>})}</div></Panel><Panel title="YouTube quota" description="Daily search budget · resets at midnight UTC."><div className="quota-value"><strong>{format(used)}</strong><span>/ 10,000 units</span></div><Progress value={used/100}/><div className="quota-details"><span>{format(10000-used)} remaining</span><span>100 units / search</span></div><div className="quiet-note">Quota is checked before every API call. Exhaustion stops the job with exit code 2. Synthetic fixtures consume no API quota.</div></Panel></div>
 <div className="workspace-strip"><Database size={16}/><span>Local embedding index</span><strong>{(data.embedding_bytes/1024/1024).toFixed(2)} MB</strong><span className="muted">Licence and attribution travel with every export.</span></div></>
}
export function Analytics(){
 const {data,error}=useRemote<State>("state");
 if(!data)return <><ErrorBox message={error}/><Loading/></>;
 return <><PageHeader title="A closer look." description="Understand yield, quality, and the sources behind your datasets."/><ErrorBox message={error}/><div className="two-column"><Panel title="Yield over batches" description="Chronological batches · frames at each stage."><BatchHistory batches={data.batches}/></Panel><Panel title="QA precision" description="Reviewed samples only · target ≥90%."><BatchHistory batches={data.batches} precision/></Panel><Panel title="CLIP score distribution" description="All scored frames, in cosine similarity bands."><Distribution data={data.distribution}/></Panel><Panel title="Source mix" description="Global harvested rows by source."><MixChart data={data.sources}/></Panel><Panel title="Licence mix" description="Global harvested rows by declared rights."><MixChart data={data.licences}/></Panel><Panel title="YouTube quota over time" description="Persisted daily counters · UTC · 10,000 unit ceiling."><QuotaHistory data={data.quota}/>{!data.quota.length?<p className="muted">No live API usage recorded.</p>:null}</Panel></div><p className="quiet-note">Synthetic fixture batches are included and labeled throughout the workspace. Fake scores and QA verdicts do not measure model quality.</p></>
}

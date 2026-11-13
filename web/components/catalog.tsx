"use client";
import {useState} from "react";
import {useAdmin} from "./admin-session";
import {useRouter,useSearchParams} from "next/navigation";
import Link from "next/link";
import {Download,ArrowUpRight,ShieldCheck,LockKeyhole,Check,Database} from "lucide-react";
import {Button} from "@/components/ui/button";
import {Badge} from "@/components/ui/badge";
import {Input} from "@/components/ui/input";
import {PageHeader,Panel,ErrorBox,RemoteStatus,Fixture} from "./common";
import {asset,format,post,useRemote} from "@/lib/client";
import type {Package,State,Discovery} from "@/lib/types";
export function Catalog(){
 const admin=useAdmin();const router=useRouter();const params=useSearchParams();
 const query=params.toString();
 const {data:results,error,refresh:retry}=useRemote<Discovery>("datasets?"+query);
 const {data,error:archiveError,refresh}=useRemote<State>(admin?"state":null);
 function apply(event:React.FormEvent<HTMLFormElement>){
  event.preventDefault();const next=new URLSearchParams();
  for(const [key,value] of new FormData(event.currentTarget))if(String(value).trim())next.set(key,String(value));
  router.replace("/datasets?"+next.toString());
 }
 const {data:demos}=useRemote<Discovery>("demo");
 const archive=data?.packages.filter(p=>!p.sale_cleared||p.synthetic)||[];
 return <><PageHeader title="Data with a paper trail." description="Discover traceable datasets. Clear rights, complete attribution, transparent prices."/>
 <div className="catalog-callout"><ShieldCheck size={21}/><p><strong>Rights before revenue.</strong> Only rights-cleared Creative Commons packages appear in discovery. Platform provenance and synthetic fixtures stay in the private archive. Prices are USD listing prices. Checkout uses Stripe test mode only; no real money.</p></div>
 <form className="discovery-filters" onSubmit={apply} key={query}>
 <div className="filter-search"><label className="field-label" htmlFor="discover-q">Keyword</label><Input id="discover-q" name="q" defaultValue={params.get("q")||""} placeholder="Search name or description…"/></div>
 <div><label className="field-label" htmlFor="discover-licence">Licence</label><select id="discover-licence" name="licence" defaultValue={params.get("licence")||""}><option value="">All licences</option>{["CC0","CC-BY","CC-BY-SA","platform_public_as_is"].map(l=><option key={l}>{l}</option>)}</select></div>
 <div><label className="field-label" htmlFor="discover-source">Source</label><select id="discover-source" name="source" defaultValue={params.get("source")||""}><option value="">All sources</option><option value="openverse">Openverse</option><option value="youtube">YouTube</option></select></div>
 <div><label className="field-label" htmlFor="discover-attribute">Attribute / label</label><Input id="discover-attribute" name="attribute" defaultValue={params.get("attribute")||""} placeholder="e.g. safety glasses"/></div>
 <div><label className="field-label">Image count</label><div className="range-fields"><Input aria-label="Minimum images" type="number" min={0} name="min_size" defaultValue={params.get("min_size")||""} placeholder="Min"/><Input aria-label="Maximum images" type="number" min={0} name="max_size" defaultValue={params.get("max_size")||""} placeholder="Max"/></div></div>
 <div><label className="field-label">Price · USD</label><div className="range-fields"><Input aria-label="Minimum price" type="number" min={0} step=".01" name="min_price" defaultValue={params.get("min_price")||""} placeholder="Min"/><Input aria-label="Maximum price" type="number" min={0} step=".01" name="max_price" defaultValue={params.get("max_price")||""} placeholder="Max"/></div></div>
 <div><label className="field-label" htmlFor="discover-sort">Sort by</label><select id="discover-sort" name="sort" defaultValue={params.get("sort")||"newest"}><option value="newest">Newest</option><option value="largest">Largest</option><option value="price_low">Price: low to high</option><option value="price_high">Price: high to low</option></select></div>
 <div className="filter-actions"><label><input name="free" type="checkbox" value="true" defaultChecked={params.get("free")==="true"}/> Free only</label><Button type="submit">Apply filters</Button><Button variant="ghost" onClick={()=>router.replace("/datasets")}>Reset</Button></div></form>
 {results?<ErrorBox message={error} retry={retry}/>:null}<div className="section-heading"><span>{results?.total??"…"} DATASETS FOUND</span><span>Filters combine and are evaluated in SQLite</span></div>
 {!results?<RemoteStatus error={error} retry={retry}/>:results.items.length?<div className="catalog-grid">{results.items.map(p=><DatasetCard key={p.id} dataset={p} refresh={refresh} owner={admin}/>)}</div>:<Panel title="No datasets match yet." description="Try broader filters, or package a rights-cleared, non-synthetic dataset."><p className="quiet-note">YouTube platform_public_as_is is recorded provenance, not permission to sell. Those packages remain unavailable for sale.</p></Panel>}
 {results&&results.total>results.limit?<div className="pagination"><span>Page {results.page} of {Math.ceil(results.total/results.limit)}</span><div className="button-row">{[-1,1].map(delta=><Button key={delta} variant="outline" disabled={delta<0?results.page===1:results.page*results.limit>=results.total} onClick={()=>{const next=new URLSearchParams(query);next.set("page",String(results.page+delta));router.replace("/datasets?"+next)}}>{delta<0?"Previous":"Next"}</Button>)}</div></div>:null}
 {demos?.items.length?<><div className="section-heading archive-heading"><span>DEMO DATASETS · SYNTHETIC · NOT FOR SALE</span></div><div className="catalog-grid">{demos.items.map(p=><DatasetCard key={p.id} dataset={p} refresh={refresh}/>)}</div></>:null}
 {admin?<><div className="section-heading archive-heading"><span>PRIVATE PACKAGE ARCHIVE</span><span>Not offered for sale · owner exports</span></div>
 {!data?<RemoteStatus error={archiveError} retry={refresh}/>:archive.length?<div className="catalog-grid">{archive.map(p=><DatasetCard key={p.id} dataset={p} refresh={refresh} owner={admin}/>)}</div>:<p className="quiet-note">No private packages. <Link href="/new" className="text-link">Create a dataset <ArrowUpRight size={13}/></Link></p>}</>:null}
 </>}

function DatasetCard({dataset:p,refresh,owner=false}:{dataset:Package;refresh:()=>Promise<void>;owner?:boolean}){
 const [price,setPrice]=useState(String(p.price));const [error,setError]=useState("");const [saved,setSaved]=useState(false);const [busy,setBusy]=useState(false);
 const eligible=p.sale_cleared&&!p.synthetic;
 async function save(){setError("");setSaved(false);setBusy(true);try{await post("price",{package:p.id,price:Number(price)});setSaved(true);await refresh()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 return <article className="dataset-card"><div className="dataset-card-top"><span className="dataset-icon"><Database size={22}/></span><Fixture synthetic={p.synthetic}/></div><h2><Link href={"/datasets/"+p.id}>{p.prompt}</Link></h2><Link href={"/batches/"+p.batch_id} className="text-link">Batch {p.batch_id.slice(0,10)} <ArrowUpRight size={12}/></Link><div className="dataset-metrics"><div><strong>{format(p.count)}</strong><span>labeled images</span></div><div><strong>{format(p.train)} / {format(p.validation)}</strong><span>train / validation</span></div></div><div className="dataset-rights"><label>DECLARED LICENCES</label><div className="subline">{p.licences.map(l=><Badge key={l} variant="outline">{l}</Badge>)}</div><p>{p.licences.includes("CC-BY-SA")?"Credit each author, link the licence, indicate changes, and apply ShareAlike.":p.licences.includes("CC-BY")?"Credit each author, link the licence, and indicate changes.":"CC0 has no attribution condition; source attribution remains in the manifest."}</p>{!p.sale_cleared?<p className="rights-warning"><LockKeyhole size={12}/>platform_public_as_is does not grant resale rights. Rights review required.</p>:null}{p.synthetic?<p className="rights-warning">Synthetic fixture · demonstration package only, not for sale.</p>:null}<details><summary>Attribution records ({p.attributions.length})</summary><ul>{p.attributions.map((a,i)=><li key={i}>{typeof a==="string"?a:(a as {creator:string}).creator}</li>)}</ul></details></div><div className="dataset-provenance"><label>PROVENANCE HASH</label><code>{p.provenance_hash}</code><span>Version {p.version}</span></div><div className="catalog-price">{p.price===0?"Free":"$"+p.price.toFixed(2)}</div>{owner?<div className="price-row"><div><label htmlFor={"price-"+p.id}>Draft price · USD</label><Input id={"price-"+p.id} aria-label={"Price for "+p.prompt} type="number" min={0} max={1000000} step={.01} value={price} onChange={e=>{setPrice(e.target.value);setSaved(false)}} disabled={!eligible}/></div><Button variant="outline" disabled={!eligible||busy} onClick={save}>{saved?<><Check/>Saved</>:busy?"Saving…":"Save price"}</Button></div>:null}<ErrorBox message={error}/>{owner?<div className="dataset-downloads"><Button variant="outline" render={<a href={asset({kind:"manifest",package:p.id})}/>} nativeButton={false}><Download/>Manifest CSV</Button><Button render={<a href={asset({kind:"images",package:p.id})}/>} nativeButton={false}><Download/>Images ZIP</Button></div>:<Button className="w-full mt-4" render={<Link href={"/datasets/"+p.id}/>} nativeButton={false}>View dataset and rights <ArrowUpRight/></Button>}</article>
}

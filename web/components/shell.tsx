"use client";
import Link from "next/link";
import {usePathname,useRouter} from "next/navigation";
import {Layers3,LayoutDashboard,Plus,Database,ChartNoAxesCombined,FolderOpen,Menu,ArrowUpRight,ShieldCheck} from "lucide-react";
import {useState} from "react";
import {useAdmin,useSessionRefresh} from "./admin-session";
import {GuidedTour} from "./guided-tour";
import {Button} from "@/components/ui/button";
const links=[{href:"/",label:"Overview",icon:LayoutDashboard},{href:"/new",label:"New dataset",icon:Plus},{href:"/batches",label:"Batches",icon:Layers3},{href:"/datasets",label:"Dataset catalog",icon:Database},{href:"/analytics",label:"Analytics",icon:ChartNoAxesCombined}];
export function Shell({children}:{children:React.ReactNode}){
 const admin=useAdmin();const router=useRouter();const refreshSession=useSessionRefresh();
 const pathname=usePathname();const [open,setOpen]=useState(false);
 return <div className="app-shell"><header className="mobile-header"><Link href="/" className="brand"><Layers3/>Foundry</Link><Button variant="ghost" size="icon" aria-label="Toggle navigation" onClick={()=>setOpen(!open)}><Menu/></Button></header>
 <aside className={"sidebar "+(open?"is-open":"")}><Link href="/" className="brand"><span className="brand-mark"><Layers3 size={29}/></span>Foundry<span className="brand-dot">.</span></Link><div className="workspace-label">WORKSPACE</div>
 <nav aria-label="Main navigation">{links.map(({href,label,icon:Icon})=><Link key={href} href={href} onClick={()=>setOpen(false)} className={(href==="/" ? pathname==="/" : pathname.startsWith(href))?"nav-link active":"nav-link"}><Icon size={18}/>{label}{href==="/new"?<span className="nav-plus">+</span>:null}</Link>)}</nav>
 <div className="sidebar-note"><ShieldCheck size={19}/><div><strong>Provenance by default</strong><p>Every frame. Every source.</p></div></div>
 <div className="auth-navigation">{admin?<Button variant="outline" onClick={async()=>{await fetch("/api/auth/logout",{method:"POST"});await refreshSession();router.replace("/login");router.refresh()}}>Sign out</Button>:<Link href="/login">Admin sign in</Link>}</div><div className="workspace-footer"><FolderOpen size={18}/><div>Local workspace<span><i/> CLI bridge</span></div><ArrowUpRight size={14}/></div></aside>
 <main className="main-content"><a className="skip-link" href="#page-main">Skip to content</a><div id="page-main" tabIndex={-1}>{children}</div>{admin?<GuidedTour/>:null}<footer className="page-footer"><span>FOUNDRY <span className="footer-dot">/</span> A clearer path from source to dataset.</span><span>Local-first · Traceable by design</span></footer></main></div>
}

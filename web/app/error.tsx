"use client";
import Link from "next/link";
import {useEffect} from "react";
import {Button} from "@/components/ui/button";
export default function ErrorPage({error,reset}:{error:Error&{digest?:string};reset:()=>void}){
 useEffect(()=>{console.error(JSON.stringify({event:"page_failed",digest:error.digest||"unavailable"}))},[error.digest]);
 return <section className="empty-state" role="alert"><h1>This page couldn’t load.</h1><p>Your saved datasets are unchanged. Retry the page or return to the catalog.</p><Button onClick={reset}>Try again</Button><Link className="text-link mt-5" href="/datasets">Dataset catalog</Link></section>
}

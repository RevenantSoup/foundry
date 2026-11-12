import type {Metadata} from "next";
import {DatasetDetail} from "@/components/dataset-detail";
import {bridge} from "@/lib/server";
export async function generateMetadata({params}:{params:Promise<{id:string}>}):Promise<Metadata>{
 const {id}=await params;
 try{
  const dataset=await bridge<{name:string;description:string;saleable:boolean}>("seo",{id});
  return {title:dataset.name,description:dataset.description.slice(0,160),alternates:{canonical:"/datasets/"+id},
   robots:{index:dataset.saleable,follow:dataset.saleable},
   openGraph:{title:dataset.name,description:dataset.description.slice(0,160),url:"/datasets/"+id},
   twitter:{title:dataset.name,description:dataset.description.slice(0,160)}};
 }catch{return {title:"Dataset unavailable",robots:{index:false,follow:false}}}
}
export default async function Page({params}:{params:Promise<{id:string}>}){return <DatasetDetail id={(await params).id}/>}

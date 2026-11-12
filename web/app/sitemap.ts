import type {MetadataRoute} from "next";
import {siteUrl} from "@/lib/site";
import {bridge} from "@/lib/server";
export const dynamic="force-dynamic";
export default async function sitemap():Promise<MetadataRoute.Sitemap>{
 const base=siteUrl();
 const urls:MetadataRoute.Sitemap=[{url:new URL("/datasets",base).toString()}];
 try{const records=await bridge<{id:string;created_at:string}[]>("seo");
 for(const row of records)urls.push({url:new URL("/datasets/"+row.id,base).toString(),lastModified:row.created_at})}catch{}
 return urls;
}

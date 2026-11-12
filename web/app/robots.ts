import type {MetadataRoute} from "next";
import {siteUrl} from "@/lib/site";
export default function robots():MetadataRoute.Robots{return {rules:{userAgent:"*",allow:["/datasets"],disallow:["/login","/dashboard","/new","/batches","/qa","/analytics","/api/"]},sitemap:new URL("/sitemap.xml",siteUrl()).toString()}}

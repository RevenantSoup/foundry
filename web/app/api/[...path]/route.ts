import {apiError} from "@/lib/responses";
import {reportError} from "@/lib/logger";
import {NextRequest,NextResponse} from "next/server";
import {promises as fs} from "node:fs";
import path from "node:path";
import {randomUUID} from "node:crypto";
import {assetResponse} from "@/lib/assets";
import {workerConfigured,WorkerError} from "@/lib/worker";
import {bridge,dataRoot,startJob,jobStatus,validId} from "@/lib/server";

export const runtime="nodejs";
export const dynamic="force-dynamic";
export const maxDuration=300;
type Context={params:Promise<{path:string[]}>};
function errorResponse(error:unknown) {void reportError(error);return apiError(error instanceof WorkerError&&error.status===503?"database_unavailable":"request_failed",error instanceof WorkerError?error.message:"Request could not be completed. Check the inputs and retry.",error instanceof WorkerError?error.status:400)}
export async function GET(request:NextRequest,context:Context) {
 try {
  const parts=(await context.params).path;
  if(parts[0]==="runtime")return NextResponse.json({remote:workerConfigured()});
  if(parts[0]==="state")return NextResponse.json(await bridge("state"));
  if(parts[0]==="batches"&&parts[1])return NextResponse.json(await bridge("batch",{batch:validId(parts[1])}));
  if(parts[0]==="jobs"&&parts[1])return NextResponse.json(await jobStatus(parts[1]));
  if(parts[0]==="asset"){
    if(request.nextUrl.searchParams.getAll("kind").length!==1)throw new Error("Specify exactly one asset kind");
    const payload=Object.fromEntries(request.nextUrl.searchParams.entries());
    return await assetResponse(payload);
  }
  return apiError("not_found","API route not found.",404);
 }catch(error){return errorResponse(error)}
}
export async function POST(request:NextRequest,context:Context) {
 try {
  // Owner mutations require the existing dashboard session and same-origin requests.
  const origin=request.headers.get("origin");
  if(origin && new URL(origin).host!==request.headers.get("host"))throw new Error("Cross-origin requests are not allowed");
  const parts=(await context.params).path;
  if(parts[0]==="plan"){
    const form=await request.formData();
    const files=form.getAll("refs");
    if(files.length!==6||files.some(f=>!(f instanceof File)||!f.type.startsWith("image/")||f.size>10*1024*1024))throw new Error("Upload exactly six images, each no larger than 10 MB");
    if(workerConfigured()){
      if((files as File[]).reduce((size,file)=>size+file.size,0)>3*1024*1024)throw new Error("References exceed the hosted upload limit");
      const refs=await Promise.all((files as File[]).map(async file=>({data:Buffer.from(await file.arrayBuffer()).toString("base64")})));
      return NextResponse.json(await bridge("refs_plan",{refs,prompt:String(form.get("prompt")||""),target:Number(form.get("target")||200),threshold:Number(form.get("threshold")||.28),live:form.get("live")==="true"}));
    }
    const upload=randomUUID();const directory=path.join(dataRoot,"web/refs",upload);
    await fs.mkdir(directory,{recursive:true});
    for(const [i,file] of (files as File[]).entries())await fs.writeFile(path.join(directory,String(i)+".image"),Buffer.from(await file.arrayBuffer()));
    try {
      const result=await bridge("plan",{upload,prompt:String(form.get("prompt")||""),target:Number(form.get("target")||200),threshold:Number(form.get("threshold")||.28),live:form.get("live")==="true"});
      return NextResponse.json(result);
    }catch(error){await fs.rm(directory,{recursive:true,force:true});throw error}
  }
  if(parts[0]==="batches"&&parts[1]&&parts[2]==="actions"){
    const body=await request.json();
    return NextResponse.json(await startJob(parts[1],body.action,body));
  }
  if(parts[0]==="price")return NextResponse.json(await bridge("price",await request.json()));
  return apiError("not_found","API route not found.",404);
 }catch(error){return errorResponse(error)}
}

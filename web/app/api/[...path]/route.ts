import {NextRequest,NextResponse} from "next/server";
import {promises as fs} from "node:fs";
import {createReadStream} from "node:fs";
import {Readable} from "node:stream";
import path from "node:path";
import {randomUUID} from "node:crypto";
import {bridge,dataRoot,startJob,jobStatus,validId} from "@/lib/server";

export const runtime="nodejs";
export const dynamic="force-dynamic";
type Context={params:Promise<{path:string[]}>};
function errorResponse(error:unknown) {return NextResponse.json({error:error instanceof Error?error.message:"Request failed"},{status:400})}
export async function GET(request:NextRequest,context:Context) {
 try {
  const parts=(await context.params).path;
  if(parts[0]==="state")return NextResponse.json(await bridge("state"));
  if(parts[0]==="batches"&&parts[1])return NextResponse.json(await bridge("batch",{batch:validId(parts[1])}));
  if(parts[0]==="jobs"&&parts[1])return NextResponse.json(await jobStatus(parts[1]));
  if(parts[0]==="asset"){
    const payload=Object.fromEntries(request.nextUrl.searchParams.entries());
    const asset=await bridge<{path:string;mime:string;filename:string}>("asset",payload);
    const stat=await fs.stat(asset.path);
    const stream=Readable.toWeb(createReadStream(asset.path)) as ReadableStream<Uint8Array>;
    return new Response(stream,{headers:{"Content-Type":asset.mime,"Content-Length":String(stat.size),"Content-Disposition":(asset.mime.startsWith("image/")?"inline":"attachment")+'; filename="'+asset.filename+'"',"Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff"}});
  }
  return NextResponse.json({error:"Not found"},{status:404});
 }catch(error){return errorResponse(error)}
}
export async function POST(request:NextRequest,context:Context) {
 try {
  // The app is local-only and unauthenticated. Refuse cross-origin mutations.
  const origin=request.headers.get("origin");
  if(origin && new URL(origin).host!==request.headers.get("host"))throw new Error("Cross-origin requests are not allowed");
  const parts=(await context.params).path;
  if(parts[0]==="plan"){
    const form=await request.formData();
    const files=form.getAll("refs");
    if(files.length!==6||files.some(f=>!(f instanceof File)||!f.type.startsWith("image/")||f.size>10*1024*1024))throw new Error("Upload exactly six images, each no larger than 10 MB");
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
  return NextResponse.json({error:"Not found"},{status:404});
 }catch(error){return errorResponse(error)}
}

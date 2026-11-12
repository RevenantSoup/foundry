import {apiError} from "@/lib/responses";
import {NextResponse} from "next/server";
import {bridge,validId} from "@/lib/server";
import type {Dataset} from "@/lib/types";
export const runtime="nodejs";
export const dynamic="force-dynamic";
export async function GET(_:Request,{params}:{params:Promise<{id:string}>}){
 try{
  const id=validId((await params).id);
  const dataset=await bridge<Dataset>("dataset",{id});
  return NextResponse.json({dataset_id:id,licences:dataset.licences,attribution:dataset.attributions},
   {headers:{"Content-Disposition":'attachment; filename="'+id+'-attribution.json"',"Cache-Control":"no-store"}});
 }catch(error){return apiError("attribution_unavailable",(error as Error).message,404)}
}

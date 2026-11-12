import {apiError} from "@/lib/responses";
import {NextResponse} from "next/server";
import {bridge,validId} from "@/lib/server";
export const runtime="nodejs";
export const dynamic="force-dynamic";
export async function GET(_:Request,{params}:{params:Promise<{id:string}>}){
 try{const id=validId((await params).id);return NextResponse.json(await bridge("dataset",{id,manifest:true}),
 {headers:{"Content-Disposition":'attachment; filename="'+id+'-manifest.json"',"Cache-Control":"no-store"}})}
 catch(error){return apiError("manifest_unavailable",(error as Error).message,400)}
}

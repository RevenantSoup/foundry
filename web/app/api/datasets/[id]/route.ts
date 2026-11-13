import {apiError} from "@/lib/responses";
import {NextResponse} from "next/server";
import {WorkerError} from "@/lib/worker";
import {bridge,validId} from "@/lib/server";
export const runtime="nodejs";
export const dynamic="force-dynamic";
export async function GET(_:Request,{params}:{params:Promise<{id:string}>}){
 try{return NextResponse.json(await bridge("dataset",{id:validId((await params).id)}))}
 catch(error){return error instanceof WorkerError&&error.status>=500?apiError("database_unavailable",error.message,error.status):apiError("dataset_unavailable","Dataset was not found or is unavailable.",404)}
}

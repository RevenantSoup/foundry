import {NextResponse} from "next/server";
import {bridge,validId} from "@/lib/server";
export const runtime="nodejs";
export const dynamic="force-dynamic";
export async function GET(_:Request,{params}:{params:Promise<{id:string}>}){
 try{return NextResponse.json(await bridge("dataset",{id:validId((await params).id)}))}
 catch(error){return NextResponse.json({error:(error as Error).message},{status:404})}
}

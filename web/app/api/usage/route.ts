import {NextResponse} from "next/server";
import {bridge} from "@/lib/server";
export const runtime="nodejs";
export const dynamic="force-dynamic";
export async function GET(){
 try{return NextResponse.json(await bridge("usage"))}
 catch(error){return NextResponse.json({error:(error as Error).message},{status:500})}
}

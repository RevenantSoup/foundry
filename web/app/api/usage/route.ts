import {apiError} from "@/lib/responses";
import {NextResponse} from "next/server";
import {bridge} from "@/lib/server";
export const runtime="nodejs";
export const dynamic="force-dynamic";
export async function GET(){
 try{return NextResponse.json(await bridge("usage"))}
 catch(error){return apiError("usage_unavailable",(error as Error).message,500)}
}

import {NextResponse} from "next/server";
import {bridge} from "@/lib/server";
import {reportError} from "@/lib/logger";
export const runtime="nodejs";
export const dynamic="force-dynamic";
export async function GET(){
 const version=process.env.APP_VERSION||"0.1.0";
 try{await bridge("health");return NextResponse.json({status:"ok",db:"ok",version},{headers:{"Cache-Control":"no-store"}})}
 catch(error){void reportError(error,"health_failed");return NextResponse.json({status:"ok",db:"error",version,error:"database_unavailable",message:"The dataset store is unavailable."},{status:503,headers:{"Cache-Control":"no-store"}})}
}

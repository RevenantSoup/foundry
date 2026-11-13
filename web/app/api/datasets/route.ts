import {apiError} from "@/lib/responses";
import {NextRequest,NextResponse} from "next/server";
import {WorkerError} from "@/lib/worker";
import {bridge} from "@/lib/server";
export const runtime="nodejs";
export const dynamic="force-dynamic";
export async function GET(request:NextRequest){
 try{return NextResponse.json(await bridge("discovery",Object.fromEntries(request.nextUrl.searchParams)))}
 catch(error){return error instanceof WorkerError&&error.status>=500?apiError("database_unavailable",error.message,error.status):apiError("invalid_query","Invalid dataset filters. Check the filters and retry.",error instanceof WorkerError?error.status:400)}
}

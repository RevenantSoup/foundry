import {apiError} from "@/lib/responses";
import {NextRequest,NextResponse} from "next/server";
import {bridge} from "@/lib/server";
export const runtime="nodejs";
export const dynamic="force-dynamic";
export async function GET(request:NextRequest){
 try{return NextResponse.json(await bridge("discovery",Object.fromEntries(request.nextUrl.searchParams)))}
 catch(error){return apiError("invalid_query",(error as Error).message,400)}
}

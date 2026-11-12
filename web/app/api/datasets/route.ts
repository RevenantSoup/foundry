import {NextRequest,NextResponse} from "next/server";
import {bridge} from "@/lib/server";
export const runtime="nodejs";
export const dynamic="force-dynamic";
export async function GET(request:NextRequest){
 try{return NextResponse.json(await bridge("discovery",Object.fromEntries(request.nextUrl.searchParams)))}
 catch(error){return NextResponse.json({error:(error as Error).message},{status:400})}
}

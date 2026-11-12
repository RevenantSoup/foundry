import {NextResponse} from "next/server";
import {bridge} from "@/lib/server";
import {apiError} from "@/lib/responses";
export const dynamic="force-dynamic";
export async function GET(){try{return NextResponse.json(await bridge("demo"))}catch{return apiError("demo_unavailable","Demo records are unavailable.",503)}}

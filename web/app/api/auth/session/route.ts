import {NextRequest,NextResponse} from "next/server";
import {verifySession,SESSION_COOKIE} from "@/lib/auth";
export async function GET(request:NextRequest){return NextResponse.json(
 {authenticated:verifySession(request.cookies.get(SESSION_COOKIE)?.value)},{headers:{"Cache-Control":"no-store"}})}

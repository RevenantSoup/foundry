import {NextRequest,NextResponse} from "next/server";
import {SESSION_COOKIE,cookieOptions} from "@/lib/auth";
import {apiError,sameOrigin} from "@/lib/responses";
export async function POST(request:NextRequest){
 if(!sameOrigin(request))return apiError("forbidden","Cross-origin logout is not allowed.",403);
 const response=NextResponse.json({authenticated:false},{headers:{"Cache-Control":"no-store"}});
 response.cookies.set(SESSION_COOKIE,"",{...cookieOptions(),maxAge:0});return response;
}

import {NextRequest,NextResponse} from "next/server";
import {authConfigured,checkCredentials,createSession,SESSION_COOKIE,cookieOptions} from "@/lib/auth";
import {apiError,sameOrigin} from "@/lib/responses";
import {log} from "@/lib/logger";
export const runtime="nodejs";
let attempts={count:0,reset:0};
export async function POST(request:NextRequest){
 if(!sameOrigin(request))return apiError("forbidden","Cross-origin login is not allowed.",403);
 if(!authConfigured())return apiError("auth_not_configured","Set the admin username, a password of at least 12 characters, and a session secret of at least 32 characters.",503);
 const now=Date.now();
 if(attempts.reset<=now)attempts={count:0,reset:now+600000};
 if(attempts.count>=10)return apiError("login_rate_limited","Too many login attempts. Try again in 10 minutes.",429);
 attempts.count+=1; // Bound all attempts globally; forwarded headers cannot bypass this single-admin limit.
 try{
  const body=await request.json();
  if(typeof body.user!=="string"||typeof body.password!=="string"||body.user.length>200||body.password.length>1000||!checkCredentials(body.user,body.password)){
   log("info","admin_login_failed");return apiError("invalid_credentials","Invalid username or password.",401);
  }
  attempts={count:0,reset:0};log("info","admin_login_succeeded");
  const response=NextResponse.json({authenticated:true},{headers:{"Cache-Control":"no-store"}});
  response.cookies.set(SESSION_COOKIE,createSession(),cookieOptions());return response;
 }catch{return apiError("invalid_request","Send a valid login request.",400)}
}

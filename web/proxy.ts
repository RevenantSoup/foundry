import {NextRequest,NextResponse} from "next/server";
import {SESSION_COOKIE,verifySession} from "@/lib/auth";
function protectedRoute(request:NextRequest){
 const p=request.nextUrl.pathname;
 if(p.startsWith("/api/v1/")||p==="/api/health"||p.startsWith("/api/auth/"))return false;
 if(p.startsWith("/api/datasets")||p==="/api/demo")return request.method!=="GET"&&request.method!=="HEAD";
 if(p==="/api/asset")return request.nextUrl.searchParams.getAll("kind").length!==1||request.nextUrl.searchParams.get("kind")!=="sample";
 if(p.startsWith("/api/"))return true;
 if(p==="/datasets"||p.startsWith("/datasets/"))return request.nextUrl.searchParams.get("admin")==="1";
 return p==="/"||["/dashboard","/new","/batches","/qa","/analytics"].some(prefix=>p===prefix||p.startsWith(prefix+"/"));
}
export function proxy(request:NextRequest){
 if(!protectedRoute(request)||verifySession(request.cookies.get(SESSION_COOKIE)?.value))return NextResponse.next();
 if(request.nextUrl.pathname.startsWith("/api/"))return NextResponse.json(
  {error:"authentication_required",message:"Sign in to the admin dashboard."},{status:401,headers:{"Cache-Control":"no-store"}});
 const url=new URL("/login",request.url);url.searchParams.set("next",request.nextUrl.pathname+request.nextUrl.search);
 return NextResponse.redirect(url);
}
export const config={matcher:["/((?!_next/static|_next/image|icon.svg|favicon.ico).*)"]};

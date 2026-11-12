import {NextResponse} from "next/server";
import {redact} from "./logger";
export function apiError(code:string,message:string,status=400){return NextResponse.json({error:code,message:redact(message)},{status,headers:{"Cache-Control":"no-store"}})}
export function sameOrigin(request:Request){
 const origin=request.headers.get("origin");
 if(!origin)return true;
 try{return new URL(origin).host===request.headers.get("host")}catch{return false}
}

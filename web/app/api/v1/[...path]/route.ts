import {NextRequest,NextResponse} from "next/server";
import {bridge} from "@/lib/server";
export const runtime="nodejs";
export const dynamic="force-dynamic";
type Context={params:Promise<{path:string[]}>};
type Result={status:number;body:unknown;headers:Record<string,string>};
async function dispatch(request:NextRequest,context:Context,post=false){
 try{
  const parts=(await context.params).path;
  const authorization=request.headers.get("authorization");
  const token=authorization?.startsWith("Bearer ")?authorization.slice(7):request.headers.get("x-api-key");
  const checkout=post&&parts.length===1&&parts[0]==="checkout";
  const datasets=!post&&parts[0]==="datasets"&&(parts.length<=2||(parts.length===3&&parts[2]==="manifest"));
  const result=await bridge<Result>("buyer",{token,checkout,unknown:!checkout&&!datasets,
    id:datasets?parts[1]:undefined,manifest:parts[2]==="manifest",params:Object.fromEntries(request.nextUrl.searchParams)});
  return NextResponse.json(result.body,{status:result.status,headers:result.headers});
 }catch{return NextResponse.json({error:"buyer_api_unavailable"},{status:503})}
}
export const GET=(request:NextRequest,context:Context)=>dispatch(request,context);
export const POST=(request:NextRequest,context:Context)=>dispatch(request,context,true);
// PLACEHOLDER: checkout only returns 501 after buyer-key validation. No payment provider exists.

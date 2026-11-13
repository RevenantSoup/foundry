import {buyerToken,paymentResponse} from "@/lib/payments";
export const runtime="nodejs";
export const dynamic="force-dynamic";
export async function GET(request:Request,{params}:{params:Promise<{id:string}>}){
 return paymentResponse({op:"order",id:(await params).id,token:buyerToken(request)});
}

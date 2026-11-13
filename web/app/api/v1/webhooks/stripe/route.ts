import {paymentResponse} from "@/lib/payments";
import {apiError} from "@/lib/responses";
export const runtime="nodejs";
export const dynamic="force-dynamic";
export const maxDuration=120;
export async function POST(request:Request){
 // Pass exact bytes to Stripe's official signature verifier on the trusted backend.
 const signature=request.headers.get("stripe-signature");
 if(!signature)return apiError("invalid_webhook","A Stripe signature is required.",400);
 const reader=request.body?.getReader();const chunks:Uint8Array[]=[];let size=0;
 if(reader){for(;;){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;if(size>1024*1024){await reader.cancel();return apiError("invalid_webhook","Webhook payload is too large.",400)}chunks.push(value)}}
 const body=Buffer.concat(chunks);
 return paymentResponse({op:"webhook",raw_body:body.toString("base64"),signature});
}

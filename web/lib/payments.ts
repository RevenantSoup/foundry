import "server-only";
import {NextResponse} from "next/server";
import {bridge} from "./server";
import type {PaymentResult} from "./assets";
import {WorkerError} from "./worker";
import {apiError} from "./responses";
export function buyerToken(request:Request){const authorization=request.headers.get("authorization");return authorization?.startsWith("Bearer ")?authorization.slice(7):request.headers.get("x-api-key")}
export async function paymentResponse(payload:object){
 try{const result=await bridge<PaymentResult>("payments",payload);if(result.body.error&&!result.body.message)result.body.message=String(result.body.error).replaceAll("_"," ");return NextResponse.json(result.body,{status:result.status,headers:result.headers})}
 catch(error){return apiError("payment_service_unavailable",error instanceof WorkerError?error.message:"Payment service is unavailable. Retry with the same idempotency key.",error instanceof WorkerError?error.status:503)}
}

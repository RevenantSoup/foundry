import {paidAssetResponse} from "@/lib/assets";
import {apiError} from "@/lib/responses";
import {WorkerError} from "@/lib/worker";
export const runtime="nodejs";
export const dynamic="force-dynamic";
export const maxDuration=300;
export async function GET(request:Request){
 const query=new URL(request.url).searchParams;
 if(query.getAll("token").length!==1||query.getAll("kind").length>1)return apiError("invalid_download","Invalid download link.",403);
 const token=query.get("token");
 // Reject malformed links without depending on worker availability. Signature,
 // paid-order ownership and expiry are still checked only by the backend.
 if(!token||token.length>2048||!/^[A-Za-z0-9_-]+\.[a-f0-9]{64}$/.test(token))return apiError("invalid_download","Invalid download link.",403);
 try{return await paidAssetResponse({token:query.get("token"),kind:query.get("kind")||"images"})}
 catch(error){return apiError("download_denied",error instanceof WorkerError?error.message:"Download access was denied.",error instanceof WorkerError?error.status:403)}
}

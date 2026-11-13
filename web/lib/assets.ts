import "server-only";
import {createReadStream} from "node:fs";
import {stat} from "node:fs/promises";
import {Readable} from "node:stream";
import {bridge} from "./server";
import {workerConfigured,workerRequest,streamedResponse} from "./worker";
type Asset={path:string;mime:string;filename:string};
export type PaymentResult={status:number;body:Record<string,unknown>;headers:Record<string,string>};
export async function localFile(asset:Asset){
 const info=await stat(asset.path);
 return new Response(Readable.toWeb(createReadStream(asset.path)) as ReadableStream<Uint8Array>,{headers:{"Content-Type":asset.mime,"Content-Length":String(info.size),"Content-Disposition":(asset.mime.startsWith("image/")?"inline":"attachment")+'; filename="'+asset.filename.replace(/["\r\n]/g,"_")+'"',"Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff"}});
}
export async function assetResponse(payload:object){
 if(workerConfigured())return streamedResponse(await workerRequest("/assets",payload,true));
 return localFile(await bridge<Asset>("asset",payload));
}
export async function paidAssetResponse(payload:object){
 if(workerConfigured())return streamedResponse(await workerRequest("/paid-assets",payload,true));
 const result=await bridge<PaymentResult>("payments",{...payload,op:"download"});
 if(result.status!==200)return Response.json(result.body,{status:result.status,headers:result.headers});
 return localFile(result.body as Asset);
}

import "server-only";
import {request as httpRequest} from "node:http";
import {request as httpsRequest} from "node:https";
import {Readable} from "node:stream";
/** Server-only transport. Loopback HTTP is reserved for local integration tests. */
export class WorkerError extends Error {
 constructor(public status:number,message:string){super(message);this.name="WorkerError"}
}
export function workerConfigured(){return !!process.env.FOUNDRY_WORKER_URL}
function settings(){
 const raw=process.env.FOUNDRY_WORKER_URL||"",key=process.env.FOUNDRY_WORKER_API_KEY||"";
 let url:URL;try{url=new URL(raw)}catch{throw new WorkerError(503,"Worker configuration is invalid.")}
 const loopback=["localhost","127.0.0.1","[::1]"].includes(url.hostname);
 if((url.protocol!=="https:"&&!(url.protocol==="http:"&&loopback))||url.username||url.password||url.search||url.hash||key.length<32||key.length>256||/[^\x21-\x7e]/.test(key)||/^(fdy_|replace|change|<)/i.test(key))throw new WorkerError(503,"Worker configuration is invalid.");
 return {base:url.href.replace(/\/$/,""),key};
}
export async function workerRequest(path:string,body?:unknown,stream=false):Promise<Response>{
 const {base,key}=settings();
 // Native server-only HTTP avoids Next's patched fetch/cache layer for RPC and file streams.
 const response=await new Promise<Response>((resolve,reject)=>{
  const url=new URL(base+path);const encoded=body===undefined?undefined:Buffer.from(JSON.stringify(body));
  const request=(url.protocol==="https:"?httpsRequest:httpRequest)(url,{method:encoded?"POST":"GET",headers:{Authorization:"Bearer "+key,"Accept-Encoding":"identity",...(encoded?{"Content-Type":"application/json","Content-Length":String(encoded.length)}:{})}},incoming=>{
   incoming.once("end",()=>clearTimeout(deadline));incoming.once("close",()=>clearTimeout(deadline));
   try{
    const encoding=incoming.headers["content-encoding"];
    if(encoding&&encoding!=="identity")throw new Error("Unexpected response encoding");
    const headers=new Headers();for(const [name,value] of Object.entries(incoming.headers)){if(value!==undefined)headers.set(name,Array.isArray(value)?value.join(", "):value)}
    resolve(new Response(Readable.toWeb(incoming) as ReadableStream<Uint8Array>,{status:incoming.statusCode||502,headers}));
   }catch{clearTimeout(deadline);incoming.destroy();reject(new WorkerError(502,"Worker returned an invalid response."))}
  });
  const deadline=setTimeout(()=>request.destroy(new Error("Worker timeout")),stream?300000:120000);
  request.once("error",()=>{clearTimeout(deadline);reject(new WorkerError(503,"Worker is unreachable or the request timed out. Retry to resume the operation."))});
  request.end(encoded);
 });
 if(!response.ok){
  await response.body?.cancel();
  if(response.status===401)throw new WorkerError(503,"Worker authentication failed. Check the server configuration.");
  if(response.status>=500)throw new WorkerError(503,"Worker operation is unavailable. Retry to resume the operation.");
  throw new WorkerError([400,403,404,409,410,413,429].includes(response.status)?response.status:502,
   ({400:"Worker rejected the request.",403:"Access denied.",404:"Worker resource not found.",409:"Another operation is running. Retry shortly.",410:"Download link has expired.",413:"Upload is too large.",429:"Worker request limit reached."} as Record<number,string>)[response.status]||"Worker request failed.");
 }
 return response;
}
export async function remoteBridge<T>(mode:string,payload:object):Promise<T>{
 const response=await workerRequest("/bridge",{mode,payload});
 try{return await response.json() as T}catch{throw new WorkerError(502,"Worker returned an invalid response.")}
}
export function streamedResponse(response:Response){
 const headers=new Headers({"Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff"});
 for(const name of ["Content-Type","Content-Length","Content-Disposition"]) {const value=response.headers.get(name);if(value)headers.set(name,value)}
 return new Response(response.body,{status:response.status,headers});
}

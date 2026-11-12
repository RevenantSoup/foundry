import {createHmac,createHash,timingSafeEqual,randomBytes} from "node:crypto";
export const SESSION_COOKIE="foundry_admin";
const TTL=8*60*60;
function credentials(){
 const user=process.env.FOUNDRY_ADMIN_USER||"",password=process.env.FOUNDRY_ADMIN_PASSWORD||"",secret=process.env.FOUNDRY_SESSION_SECRET||"";
 if(!user||password.length<12||secret.length<32||/^(replace-with|change-me|<)/i.test(password)||/^(replace-with|change-me|<)/i.test(secret))return null;
 return {user,password,key:createHmac("sha256",secret).update(user+"\0"+password).digest()};
}
function equal(a:string,b:string){return timingSafeEqual(createHash("sha256").update(a).digest(),createHash("sha256").update(b).digest())}
export function authConfigured(){return credentials()!==null}
export function checkCredentials(user:string,password:string){const c=credentials();return !!c&&equal(user,c.user)&&equal(password,c.password)}
export function createSession(){
 const c=credentials();if(!c)throw new Error("Admin authentication is not configured");
 const body=Buffer.from(JSON.stringify({u:c.user,exp:Math.floor(Date.now()/1000)+TTL,n:randomBytes(16).toString("hex")})).toString("base64url");
 return body+"."+createHmac("sha256",c.key).update(body).digest("base64url");
}
export function verifySession(token?:string){
 const c=credentials();if(!c||!token||token.length>2048)return false;
 try{
  const [body,signature,extra]=token.split(".");
  if(!body||!signature||extra)return false;
  const expected=createHmac("sha256",c.key).update(body).digest("base64url");
  if(!equal(signature,expected))return false;
  const payload=JSON.parse(Buffer.from(body,"base64url").toString());
  return payload.u===c.user&&typeof payload.exp==="number"&&payload.exp>Math.floor(Date.now()/1000);
 }catch{return false}
}
export const cookieOptions=()=>({httpOnly:true,sameSite:"lax" as const,secure:process.env.NODE_ENV==="production",path:"/",maxAge:TTL});
export function safeReturn(value:string|null){return value?.startsWith("/")&&!value.startsWith("//")&&!value.includes("\\")?value:"/"}

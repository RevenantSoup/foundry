const secretNames=["FOUNDRY_ADMIN_PASSWORD","FOUNDRY_SESSION_SECRET","YOUTUBE_API_KEY","OPENAI_API_KEY","OPENVERSE_API_KEY","SENTRY_DSN"];
export function redact(value:string){
 let clean=value;for(const name of secretNames){const secret=process.env[name];if(secret)clean=clean.split(secret).join("[redacted]")}
 return clean.replace(/Bearer\s+[^\s"']+/gi,"Bearer [redacted]").replace(/fdy_[A-Za-z0-9_-]+/g,"[buyer-key-redacted]");
}
export function log(level:"info"|"error",event:string,fields:Record<string,unknown>={}){
 console[level](redact(JSON.stringify({timestamp:new Date().toISOString(),level,event,...fields})));
}
export async function reportError(error:unknown,event="request_failed"){
 const message=redact(error instanceof Error?error.message:String(error));
 log("error",event,{message});
 if(process.env.SENTRY_DSN){
  try {const sentry=await import("@sentry/node");sentry.captureException(new Error(message));}catch{}
 }
}

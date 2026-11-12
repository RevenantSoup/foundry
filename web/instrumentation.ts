export async function register(){
 if(process.env.NEXT_RUNTIME==="nodejs"&&process.env.SENTRY_DSN){
  const sentry=await import("@sentry/node");
  sentry.init({dsn:process.env.SENTRY_DSN,defaultIntegrations:false,dataCollection:{userInfo:false,cookies:false,httpHeaders:false,httpBodies:[],urlQueryParams:false},tracesSampleRate:0});
 }
}

export function siteUrl(){
 try{const url=new URL(process.env.NEXT_PUBLIC_SITE_URL||"http://localhost:3000");if(!["http:","https:"].includes(url.protocol))throw new Error();return url}
 catch{return new URL("http://localhost:3000")}
}

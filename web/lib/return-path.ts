// Only same-origin paths; never return to the login form after authentication.
export function safeReturn(value:unknown){
 if(typeof value!=="string"||!value.startsWith("/")||value.startsWith("//")||/[\\\u0000-\u0020]/.test(value))return "/dashboard";
 try{const url=new URL(value,"https://foundry.invalid");return url.origin==="https://foundry.invalid"&&url.pathname!=="/login"?url.pathname+url.search+url.hash:"/dashboard"}catch{return "/dashboard"}
}

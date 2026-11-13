import {Suspense} from "react";
import {cookies} from "next/headers";
import {redirect} from "next/navigation";
import {Login} from "@/components/login";
import {SESSION_COOKIE,verifySession} from "@/lib/auth";
import {safeReturn} from "@/lib/return-path";
export const metadata={title:"Admin sign in",robots:{index:false,follow:false}};
export default async function Page({searchParams}:{searchParams:Promise<{next?:string|string[]}>}){
 if(verifySession((await cookies()).get(SESSION_COOKIE)?.value))redirect(safeReturn((await searchParams).next||null));
 return <Suspense><Login/></Suspense>
}

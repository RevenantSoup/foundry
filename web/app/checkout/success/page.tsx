import {CheckoutReturn} from "@/components/checkout";
export const metadata={title:"Test order",robots:{index:false,follow:false}};
export default async function Page({searchParams}:{searchParams:Promise<{order?:string}>}){return <CheckoutReturn order={(await searchParams).order}/>}

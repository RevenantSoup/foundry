import {DatasetWizard} from "@/components/wizard";
export const metadata={title:"New dataset",robots:{index:false,follow:false}};
export default async function Page({searchParams}:{searchParams:Promise<{batch?:string}>}){const {batch}=await searchParams;return <DatasetWizard batch={batch}/>}

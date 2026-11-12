import {DatasetWizard} from "@/components/wizard";
export default async function Page({searchParams}:{searchParams:Promise<{batch?:string}>}){const {batch}=await searchParams;return <DatasetWizard batch={batch}/>}

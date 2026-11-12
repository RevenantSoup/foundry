import {DatasetDetail} from "@/components/dataset-detail";
export default async function Page({params}:{params:Promise<{id:string}>}){return <DatasetDetail id={(await params).id}/>}

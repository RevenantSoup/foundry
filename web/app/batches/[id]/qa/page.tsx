import {QAReviewPage} from "@/components/qa-review";
export default async function Page({params}:{params:Promise<{id:string}>}){const {id}=await params;return <QAReviewPage id={id}/>}

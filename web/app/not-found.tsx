import Link from "next/link";
export const metadata={title:"Page not found",robots:{index:false,follow:false}};
export default function NotFound(){return <section className="empty-state"><h1>Nothing at this address.</h1><p>Check the URL or browse the available datasets.</p><Link className="text-link" href="/datasets">Return to the dataset catalog</Link></section>}

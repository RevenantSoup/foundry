import type {Metadata} from "next";
import "./globals.css";
import {AdminSession} from "@/components/admin-session";
import {Shell} from "@/components/shell";
import {siteUrl} from "@/lib/site";
export const metadata:Metadata={
 metadataBase:siteUrl(),title:{default:"Foundry — Traceable image datasets",template:"%s | Foundry"},
 description:"Discover image datasets with source licences, attribution, QA records and verifiable manifest provenance.",
 openGraph:{type:"website",siteName:"Foundry",title:"Foundry",description:"Traceable image datasets, with their source rights attached.",images:["/opengraph-image"]},
 twitter:{card:"summary_large_image",title:"Foundry",description:"Traceable image datasets, with their source rights attached.",images:["/opengraph-image"]},
};
export default function RootLayout({children}:{children:React.ReactNode}) {return <html lang="en" className="dark"><body><AdminSession><Shell>{children}</Shell></AdminSession></body></html>}

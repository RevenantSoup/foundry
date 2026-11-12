import type {Metadata} from "next";
import "./globals.css";
import {Shell} from "@/components/shell";
export const metadata:Metadata={title:{default:"Foundry — Dataset workspace",template:"%s · Foundry"},description:"Build, review, and share traceable image datasets."};
export default function RootLayout({children}:{children:React.ReactNode}) {return <html lang="en" className="dark"><body><Shell>{children}</Shell></body></html>}

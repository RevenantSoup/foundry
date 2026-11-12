import {ImageResponse} from "next/og";
export const runtime="nodejs";
export const alt="Foundry — Traceable image datasets";
export const size={width:1200,height:630};
export const contentType="image/png";
export default function Image(){return new ImageResponse(<div style={{background:"#111310",color:"#f0f3ec",width:"100%",height:"100%",display:"flex",flexDirection:"column",justifyContent:"center",padding:"90px",fontFamily:"sans-serif"}}><div style={{color:"#c9f96a",fontSize:30,marginBottom:35}}>FOUNDRY</div><div style={{fontSize:76,lineHeight:1.1}}>Data with a paper trail.</div><div style={{fontSize:28,marginTop:30,color:"#a9b69b"}}>Source licences. Full attribution. Verifiable provenance.</div></div>,size)}

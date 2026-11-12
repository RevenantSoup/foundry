"use client";
import {TriangleAlert} from "lucide-react";
import {Panel,ErrorBox} from "./common";
import {format,useRemote} from "@/lib/client";
import type {Usage} from "@/lib/types";
export function UsagePanel(){
 const {data,error}=useRemote<Usage>("usage");
 if(!data)return <ErrorBox message={error}/>;
 const warning=data.youtube.used>=8000||data.youtube.provider_blocked;
 return <Panel title="Live usage & quota" description="Provider request attempts, retries and errors · persisted per UTC day."><ErrorBox message={error}/>{warning?<div className="quota-warning" role="alert"><TriangleAlert size={18}/><span>YouTube quota warning: {format(data.youtube.used)} / 10,000 used; {format(data.youtube.remaining)} remaining. Reset {data.youtube.reset_at}. Exhaustion stops jobs with exit code 2.</span></div>:null}<div className="usage-summary"><span>YouTube today</span><strong>{format(data.youtube.used)} / 10,000 units</strong><span>{format(data.youtube.remaining)} remaining</span></div><div className="table-scroll"><table className="data-table"><thead><tr><th>UTC day</th><th>Source</th><th>Quota used</th><th>Remaining</th><th>Requests</th><th>429s</th><th>Errors</th><th>Retries</th><th>Latency</th><th>Tokens</th></tr></thead><tbody>{data.daily.map(row=><tr key={row.day+row.source}><td>{row.day}</td><td>{row.source}</td><td>{row.quota_used===undefined?"—":format(row.quota_used)}</td><td>{row.quota_remaining===undefined?"—":format(row.quota_remaining)}</td><td>{row.requests}</td><td>{row.rate_limits}</td><td>{row.errors}</td><td>{row.retries}</td><td>{(row.latency_ms/1000).toFixed(2)}s</td><td>{row.tokens===null?"—":format(row.tokens)}</td></tr>)}</tbody></table></div>{!data.daily.length?<p className="quiet-note">No live provider usage yet. Offline fixtures do not consume API quota.</p>:null}<p className="field-help">Verifier tokens and request latency are recorded when available. Providers do not return billed USD cost; Foundry does not invent a cost estimate.</p></Panel>
}

import {Skeleton} from "@/components/ui/skeleton";
export default function Loading(){return <section aria-busy="true" aria-label="Loading page"><Skeleton className="h-10 w-72 mb-5"/><Skeleton className="h-4 w-96 max-w-full mb-8"/><div className="stats-grid">{[0,1,2,3,4].map(n=><Skeleton key={n} className="h-28"/>)}</div><Skeleton className="h-64 w-full"/></section>}

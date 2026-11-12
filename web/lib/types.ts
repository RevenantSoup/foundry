export interface Plan {batch_id:string;prompt:string;refs:string[];target:number;threshold:number;offline:boolean;search_terms:string[];hashtags:string[];negative_terms:string[];checklist:string[]}
export interface DatasetRow {id:string;source:string;source_url:string;licence:string;attribution:string;clip_score:number|null;vlm_verdict:string;qa_verdict:string;split:string;provenance_hash:string;captured_at:string}
export interface Package {id:string;batch_id:string;version:string;count:number;licences:string[];attributions:(string|Attribution)[];train:number;validation:number;provenance_hash:string;price:number;sale_cleared:boolean;synthetic:boolean;prompt:string}
export interface Batch {id:string;prompt:string;plan:Plan;synthetic:boolean;status:string;harvested:number;shortlisted:number;verified:number;packaged:number;qa_precision:number|null;reviewed:number;qa_passed:boolean;licences:string[];sources:string[];created_at:string|null}
export interface Detail extends Batch {rows:DatasetRow[];samples:{row_id:string;position:number;verdict:string}[];drops:{reason:string;count:number}[];packages:Package[];contact_sheet:boolean}
export interface Mix {name:string;value:number}
export interface State {batches:Batch[];totals:{batches:number;harvested:number;shortlisted:number;verified:number;packaged:number;precision:number|null};sources:Mix[];licences:Mix[];distribution:Mix[];quota:{source:string;day:string;units:number}[];packages:Package[];embedding_bytes:number}
export interface Job {id:string;batch:string;action:string;status:"queued"|"running"|"succeeded"|"failed";log:string;exit_code?:number;pid?:number}

export interface Dataset extends Package {
 name:string;description:string;attribute:string;labels:string[];sources:string[];
 price_cents:number;currency:string;manifest_sha256:string;size_bytes:number;
 created_at:string;row_count:number;saleable:boolean;unavailable_reason:string;
 attributions:{creator:string;source_url:string;licence:string;licence_url:string;title:string;source_page_url:string}[];
 samples:{id:string;url:string;licence:string;attribution:string}[];
 licence_links:{licence:string;url:string}[];qa_precision:number|null;
}
export interface Discovery {items:Dataset[];total:number;page:number;limit:number}
export interface Usage {daily:{source:string;day:string;requests:number;rate_limits:number;errors:number;retries:number;latency_ms:number;tokens:number|null;cost_usd:number|null;quota_used?:number;quota_remaining?:number}[];youtube:{used:number;remaining:number;reset_at:string;provider_blocked:boolean}}

export interface Attribution {creator:string;source_url:string;licence:string;licence_url:string;title:string;source_page_url:string}

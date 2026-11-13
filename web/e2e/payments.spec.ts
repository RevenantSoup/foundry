import {test,expect} from "@playwright/test";
import {execFileSync} from "node:child_process";
import {createHmac,randomUUID} from "node:crypto";
import path from "node:path";
import {writeFileSync} from "node:fs";
const repo=path.resolve(process.cwd(),"..");
const python=process.env.FOUNDRY_PYTHON||path.join(repo,".venv/bin/python");
const root=path.join(repo,"work/web-test-data");
let fixture:{dataset:string;key:string;revoked:string};
function code(source:string){return execFileSync(python,["-c",source],{cwd:repo,env:{...process.env,FOUNDRY_ROOT:root},encoding:"utf8"})}
const database="import os;from foundry.db import Database;d=Database(os.environ['FOUNDRY_ROOT']+'/foundry.sqlite3');";
function signed(body:string){const timestamp=Math.floor(Date.now()/1000);return `t=${timestamp},v1=${createHmac("sha256",process.env.STRIPE_WEBHOOK_SECRET!).update(timestamp+"."+body).digest("hex")}`}
function completion(order:{session_id:string;order_id:string},changes:object={}){return JSON.stringify({id:"evt_"+randomUUID(),object:"event",type:"checkout.session.completed",livemode:false,data:{object:{id:order.session_id,object:"checkout.session",mode:"payment",payment_status:"paid",livemode:false,amount_total:1999,currency:"usd",payment_intent:"pi_test_fixture",metadata:{order_id:order.order_id,dataset_id:fixture.dataset},...changes}}})}
test.beforeAll(()=>{
 fixture=JSON.parse(execFileSync(python,[path.join(repo,"web/e2e/setup-marketplace.py")],{env:{...process.env,FOUNDRY_ROOT:root},encoding:"utf8"}));
 code(database+`from foundry.marketplace import set_price;set_price(d,${JSON.stringify(fixture.dataset)},1999)`);
});
test("test Checkout API validates inputs and preserves buyer-key errors",async({request})=>{
 expect((await request.post("/api/v1/checkout",{data:{}})).status()).toBe(401);
 expect((await request.post("/api/v1/checkout",{headers:{Authorization:"Bearer "+fixture.revoked},data:{}})).status()).toBe(403);
 const headers={Authorization:"Bearer "+fixture.key};
 for(const [body,status] of [[{},400],[{dataset_id:"unknown",email:"buyer@example.test"},404],[{dataset_id:fixture.dataset,email:"bad"},400]] as const){expect((await request.post("/api/v1/checkout",{headers,data:body})).status()).toBe(status)}
 code(database+`d.conn.execute('UPDATE datasets SET price_cents=0 WHERE id=?',(${JSON.stringify(fixture.dataset)},));d.conn.commit()`);
 expect((await request.post("/api/v1/checkout",{headers,data:{dataset_id:fixture.dataset,email:"buyer@example.test"}})).status()).toBe(400);
 code(database+`d.conn.execute('UPDATE datasets SET price_cents=1999 WHERE id=?',(${JSON.stringify(fixture.dataset)},));d.conn.commit()`);
});
test("raw signed webhook alone grants one expiring dataset download",async({request})=>{
 const headers={Authorization:"Bearer "+fixture.key,"Idempotency-Key":randomUUID()};const data={dataset_id:fixture.dataset,email:"buyer@example.test"};
 const started=await request.post("/api/v1/checkout",{headers,data});expect(started.status()).toBe(200);const order=await started.json();
 expect(new URL(order.url).hostname).toBe("checkout.stripe.com");expect(order.session_id).toMatch(/^cs_test_/);
 expect(await(await request.post("/api/v1/checkout",{headers,data})).json()).toEqual(order);
 const pending=await(await request.get("/api/v1/orders/"+order.order_id,{headers})).json();expect(pending.status).toBe("pending");expect(pending.download_url).toBeUndefined();
 expect((await request.get("/api/v1/downloads?token=unknown")).status()).toBe(403);
 const raw=completion(order);
 expect((await request.post("/api/v1/webhooks/stripe",{data:raw})).status()).toBe(400);
 expect((await request.post("/api/v1/webhooks/stripe",{headers:{"stripe-signature":"invalid"},data:raw})).status()).toBe(400);
 expect((await request.post("/api/v1/webhooks/stripe",{headers:{"stripe-signature":signed(raw)},data:raw+" "})).status()).toBe(400);
 const wrong="not-json";expect((await request.post("/api/v1/webhooks/stripe",{headers:{"stripe-signature":signed(wrong)},data:wrong})).status()).toBe(400);
 const before=await(await request.get("/api/v1/orders/"+order.order_id,{headers})).json();expect(before.status).toBe("pending");
 for(let i=0;i<2;i++)expect((await request.post("/api/v1/webhooks/stripe",{headers:{"stripe-signature":signed(raw)},data:raw})).status()).toBe(200);
 const paid=await(await request.get("/api/v1/orders/"+order.order_id,{headers})).json();expect(paid.status).toBe("paid");expect(paid.expires_at).toBeGreaterThan(Date.now()/1000);expect(paid.expires_at).toBeLessThanOrEqual(Date.now()/1000+86400);
 expect(JSON.stringify(paid)).not.toContain(root);expect(JSON.stringify(paid)).not.toContain(process.env.FOUNDRY_WORKER_API_KEY!);expect(paid.download_url).toMatch(/^\/api\/v1\/downloads\?token=/);
 const zip=await request.get(paid.download_url);expect(zip.status()).toBe(200);expect((await zip.body()).subarray(0,2).toString()).toBe("PK");
 const artifact=JSON.parse(execFileSync(python,["-c",String.raw`
import csv,hashlib,io,json,sqlite3,sys,zipfile
from pathlib import Path
root=Path(sys.argv[1]);dataset=sys.argv[2];order=sys.argv[3];package=root/'packages'/dataset
archive=zipfile.ZipFile(io.BytesIO(sys.stdin.buffer.read()))
rows=list(csv.DictReader(io.StringIO(archive.read('manifest.csv').decode())))
assert len(rows)==200
assert set(archive.namelist())=={'manifest.csv','dataset.json'}|{'images/'+row['id'] for row in rows}
for name in archive.namelist():assert archive.read(name)==(package/name).read_bytes()
db=sqlite3.connect(root/'foundry.sqlite3');db.row_factory=sqlite3.Row
record=dict(db.execute('SELECT id,dataset_id,status,amount,currency,stripe_session_id FROM orders WHERE id=?',(order,)).fetchone())
assert record['status']=='paid' and record['dataset_id']==dataset and record['amount']==1999 and record['currency']=='USD'
assert db.execute('SELECT count(*) FROM download_grants WHERE order_id=?',(order,)).fetchone()[0]==1
print(json.dumps({'order':record,'download_status':200,'matched_images':len(rows),'zip_entries':len(archive.namelist()),'manifest_sha256':hashlib.sha256(archive.read('manifest.csv')).hexdigest(),'synthetic_rights_fixture':True}))
`,root,fixture.dataset,order.order_id],{cwd:repo,input:await zip.body(),encoding:"utf8"}));
 writeFileSync(path.join(repo,process.env.FOUNDRY_TEST_REMOTE==="1"?"work/phase6-remote-sales-evidence.json":"work/phase6-sales-evidence.json"),JSON.stringify(artifact,null,2)+"\n");
 const manifest=await request.get(paid.download_url+"&kind=manifest");expect(manifest.status()).toBe(200);expect(await manifest.text()).toContain("CC-BY");
 expect((await request.get(paid.download_url+"tamper")).status()).toBe(403);
 const counts=JSON.parse(code(database+`import json;print(json.dumps([d.conn.execute('SELECT count(*) FROM orders WHERE stripe_session_id=?',(${JSON.stringify(order.session_id)},)).fetchone()[0],d.conn.execute('SELECT count(*) FROM download_grants WHERE order_id=?',(${JSON.stringify(order.order_id)},)).fetchone()[0]]))`));expect(counts).toEqual([1,1]);
 code(database+`d.conn.execute("UPDATE orders SET status='pending' WHERE id=?",(${JSON.stringify(order.order_id)},));d.conn.commit()`);
 expect((await request.get(paid.download_url)).status()).toBe(403);
 code(database+`d.conn.execute("UPDATE orders SET status='paid' WHERE id=?",(${JSON.stringify(order.order_id)},));d.conn.commit()`);
 const token=paid.download_url.split("token=")[1];const parts=token.split(".");const claims=JSON.parse(Buffer.from(parts[0],"base64url").toString());claims.exp=Math.floor(Date.now()/1000)-1;
 code(database+`d.conn.execute('UPDATE download_grants SET expires_at=? WHERE order_id=?',(${claims.exp},${JSON.stringify(order.order_id)}));d.conn.commit()`);
 const encoded=Buffer.from(JSON.stringify(claims)).toString("base64url");const expired=encoded+"."+createHmac("sha256",process.env.FOUNDRY_DOWNLOAD_SECRET!).update(encoded).digest("hex");
 expect((await request.get("/api/v1/downloads?token="+expired)).status()).toBe(410);
});
test("verified mismatched Session never grants access",async({request})=>{
 const headers={Authorization:"Bearer "+fixture.key,"Idempotency-Key":randomUUID()};
 const order=await(await request.post("/api/v1/checkout",{headers,data:{dataset_id:fixture.dataset,email:"buyer@example.test"}})).json();
 const raw=completion(order,{amount_total:1});expect((await request.post("/api/v1/webhooks/stripe",{headers:{"stripe-signature":signed(raw)},data:raw})).status()).toBe(200);
 const result=await(await request.get("/api/v1/orders/"+order.order_id,{headers})).json();expect(result.status).toBe("review");expect(result.download_url).toBeUndefined();
});
test("remote transport reports only safe runtime information",async({page,request})=>{
 await page.request.post("/api/auth/login",{data:{user:process.env.FOUNDRY_ADMIN_USER,password:process.env.FOUNDRY_ADMIN_PASSWORD}});
 const response=await page.request.get("/api/runtime");expect(await response.json()).toEqual({remote:process.env.FOUNDRY_TEST_REMOTE==="1"});
 expect((await request.get("/api/health")).status()).toBe(200);
});

test("worker faults are clear and never fall back to local storage",async({request})=>{
 test.skip(process.env.FOUNDRY_TEST_REMOTE!=="1","Remote transport fault contract");
 await request.post("/api/auth/login",{data:{user:process.env.FOUNDRY_ADMIN_USER,password:process.env.FOUNDRY_ADMIN_PASSWORD}});
 const control=async(mode:string)=>{const result=await request.post("http://127.0.0.1:8100/__test__/transport",{headers:{Authorization:"Bearer "+process.env.FOUNDRY_WORKER_API_KEY},data:{mode}});expect(result.status()).toBe(200)};
 try{
  for(const [mode,expected] of [["unauthorized",503],["drop",503],["empty",502],["encoded",502]] as const){
   await control(mode);const response=await request.get("/api/state");expect(response.status()).toBe(expected);const body=await response.json();expect(body.message).toMatch(/Worker/);expect(JSON.stringify(body)).not.toContain("127.0.0.1:8100");expect(JSON.stringify(body)).not.toContain(process.env.FOUNDRY_WORKER_API_KEY!);
  }
 }finally{await control("normal")}
 expect((await request.get("/api/health")).status()).toBe(200);
});

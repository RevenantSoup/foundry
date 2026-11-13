import {test,expect} from "@playwright/test";
import {Buffer} from "node:buffer";
import {execFileSync} from "node:child_process";
import {mkdirSync,writeFileSync} from "node:fs";
import path from "node:path";

// Read the real CLI artifacts independently of the web bridge. No record mutation.
function inspectPipeline(batch:string,packageId:string){
 const repo=path.resolve(process.cwd(),"..");
 const root=process.env.FOUNDRY_ROOT||path.join(repo,"work/web-test-data");
 const source=String.raw`
import csv,hashlib,json,sqlite3,sys
from pathlib import Path
from dataclasses import asdict
from foundry.models import Row
root=Path(sys.argv[1]);batch=sys.argv[2];package=sys.argv[3]
db=sqlite3.connect(root/'foundry.sqlite3');db.row_factory=sqlite3.Row
record=db.execute('SELECT * FROM batches WHERE id=?',(batch,)).fetchone()
plan=json.loads(record['plan']);plan_path=root/'plans'/(batch+'.json')
assert json.loads(plan_path.read_text())==plan
assert plan['offline'] is True and len(plan['refs'])==6
assert all(Path(ref).is_file() for ref in plan['refs'])
assert len({hashlib.sha256(Path(ref).read_bytes()).hexdigest() for ref in plan['refs']})==6
rows=[dict(r) for r in db.execute('SELECT * FROM rows WHERE batch_id=?',(batch,))]
assert rows and all((root/'raw'/r['id']).is_file() for r in rows)
samples=[dict(r) for r in db.execute('SELECT * FROM qa_samples WHERE batch_id=? ORDER BY position',(batch,))]
assert len(samples)==200 and len({r['row_id'] for r in samples})==200
assert all(r['verdict']=='accept' for r in samples) and record['qa_passed']==1
snapshots=[dict(r) for r in db.execute('SELECT * FROM qa_files WHERE batch_id=?',(batch,))]
assert len(snapshots)==200
for snapshot in snapshots:
 assert hashlib.sha256((root/'raw'/snapshot['row_id']).read_bytes()).hexdigest()==snapshot['sha256']
qa=root/'qa'/batch
assert (qa/'contact-sheet.png').is_file() and len(list(qa.glob('*-*.png')))==201
output=root/'packages'/package
with (output/'manifest.csv').open() as stream: manifest=list(csv.DictReader(stream))
meta=json.loads((output/'dataset.json').read_text())
digest=hashlib.sha256((output/'manifest.csv').read_bytes()).hexdigest()
assert meta['manifest_sha256']==digest and meta['batch_id']==batch and meta['count']==len(manifest)==200
by_id={r['id']:r for r in rows}
for exported in manifest:
 original=by_id[exported['id']]
 assert all(str(original[key])==value for key,value in exported.items())
 assert exported['licence'] and exported['attribution'] and exported['source_url'].startswith('stub://')
 image=(output/'images'/exported['id']).read_bytes()
 assert image==(root/'raw'/exported['id']).read_bytes()
 provenance=asdict(Row(**original));provenance.pop('provenance_hash')
 provenance['sha256']=hashlib.sha256(image).hexdigest()
 assert hashlib.sha256(json.dumps(provenance,sort_keys=True).encode()).hexdigest()==exported['provenance_hash']
splits={split:sum(r['split']==split for r in manifest) for split in ('train','validation')}
assert splits=={'train':180,'validation':20}
registry=dict(db.execute('SELECT * FROM datasets WHERE id=?',(package,)).fetchone())
assert registry['manifest_sha256']==digest and registry['synthetic']==1 and registry['saleable']==0
assert 'Synthetic fixture; not for sale' in registry['unavailable_reason']
jobs=[]
for file in (root/'web'/'jobs').glob('*.json'):
 job=json.loads(file.read_text())
 if job.get('batch')==batch: jobs.append({key:job.get(key) for key in ('id','action','status','exit_code')})
assert any(j['action']=='package' and j['status']=='failed' and j['exit_code']==1 for j in jobs)
assert any(j['action']=='package' and j['status']=='succeeded' for j in jobs)
print(json.dumps({'batch_id':batch,'package_id':package,'root':str(root),'database':str(root/'foundry.sqlite3'),'plan':str(plan_path),'raw_count':len(rows),'qa_count':len(samples),'qa_snapshot_count':len(snapshots),'manifest':str(output/'manifest.csv'),'manifest_sha256':digest,'package_image_count':len(list((output/'images').iterdir())),'splits':splits,'provenance_verified':len(manifest),'jobs':jobs,'sale_stage':'BLOCKED','sale_reason':registry['unavailable_reason'],'synthetic':True,'saleable':False}))
`;
 return JSON.parse(execFileSync(process.env.FOUNDRY_PYTHON||path.join(repo,".venv/bin/python"),["-c",source,root,batch,packageId],{cwd:repo,encoding:"utf8"}));
}

test.beforeEach(async({page,request})=>{
 const credentials={user:process.env.FOUNDRY_ADMIN_USER,password:process.env.FOUNDRY_ADMIN_PASSWORD};
 await request.post("/api/auth/login",{data:credentials});
 await page.request.post("/api/auth/login",{data:credentials});
 await page.addInitScript(()=>localStorage.setItem("foundry-tour-v1-dismissed","true"));
});
test("real CLI wizard, failing QA gate, package downloads and responsive pages",async({page,request})=>{
 const errors:string[]=[];
 page.on("pageerror",error=>errors.push(error.message));
 await page.request.post("/api/auth/logout");
 await page.goto("/new");
 await expect(page.getByRole("heading",{name:"Welcome back."})).toBeVisible();
 await page.getByRole("textbox",{name:"Username",exact:true}).fill(process.env.FOUNDRY_ADMIN_USER!);
 await page.getByLabel("Password",{exact:true}).fill(process.env.FOUNDRY_ADMIN_PASSWORD!);
 await page.getByRole("button",{name:"Sign in",exact:true}).click();
 await expect(page.getByRole("heading",{name:"Start with a clear picture."})).toBeVisible();
 expect(await(await page.request.get("/api/auth/session")).json()).toEqual({authenticated:true});
 await expect(page.getByRole("button",{name:"Generate plan"})).toBeDisabled();
 const prompt="Browser fixture safety glasses "+Date.now();
 await page.getByLabel("Image specification").fill(prompt);
 // Six distinct readable PNGs generated with the CLI's installed Pillow dependency.
 const repoRoot=path.resolve(process.cwd(),"..");
 const images:string[]=JSON.parse(execFileSync(process.env.FOUNDRY_PYTHON||path.join(repoRoot,".venv/bin/python"),["-c",`import base64,io,json
from PIL import Image
images=[]
for i in range(6):
 stream=io.BytesIO();Image.new('RGB',(32,32),(30+i*35,80+i*20,220-i*25)).save(stream,format='PNG')
 images.append(base64.b64encode(stream.getvalue()).decode())
print(json.dumps(images))`],{encoding:"utf8"}));
 expect(new Set(images).size).toBe(6);
 await page.getByLabel("Reference images",{exact:true}).setInputFiles(images.map((image,i)=>({name:i+".png",mimeType:"image/png",buffer:Buffer.from(image,"base64")})));
 await page.getByRole("button",{name:"Generate plan"}).click();
 await expect(page.getByRole("heading",{name:"Your search plan"})).toBeVisible();
 const batch=new URL(page.url()).searchParams.get("batch")!;
 expect(batch).toMatch(/^[a-f0-9]{32}$/);
 await page.getByRole("button",{name:"Continue to build"}).click();
 await page.getByRole("button",{name:"Run harvest → filter"}).click();
 await expect(page.getByRole("button",{name:"Generate contact sheet"})).toBeVisible({timeout:90000});
 await page.getByRole("button",{name:"Generate contact sheet"}).click();
 await expect(page.getByRole("button",{name:"Submit 200 verdicts"})).toBeVisible({timeout:60000});
 await expect(page.locator(".crop-card")).toHaveCount(200);
 await expect(page.getByRole("button",{name:"Submit 200 verdicts"})).toBeDisabled();
 const state=await (await request.get("/api/batches/"+batch)).json();
 // Drive every per-image UI control, then deliberately fail the 90% gate.
 for(const sample of state.samples)await page.getByRole("button",{name:"Accept image "+sample.row_id,exact:true}).click();
 for(const sample of state.samples.slice(0,21))await page.getByRole("button",{name:"Reject image "+sample.row_id,exact:true}).click();
 await page.getByRole("button",{name:"Submit 200 verdicts"}).click();
 await expect(page.getByRole("alert").filter({hasText:"CLI exited 1"})).toBeVisible();
 const failedReview=await(await request.get("/api/batches/"+batch)).json();
 expect(failedReview.samples.filter((sample:{verdict:string})=>sample.verdict==="accept")).toHaveLength(179);
 expect(failedReview.samples.filter((sample:{verdict:string})=>sample.verdict==="reject")).toHaveLength(21);
 expect(failedReview.qa_precision).toBe(.895);
 expect(failedReview.qa_passed).toBe(false);
 const blocked=await request.post("/api/batches/"+batch+"/actions",{data:{action:"package"}});
 const blockedJob=await blocked.json();
 await expect.poll(async()=>(await(await request.get("/api/jobs/"+blockedJob.id)).json()).status).toBe("failed");
 const refusedPackage=await(await request.get("/api/jobs/"+blockedJob.id)).json();
 expect(refusedPackage.exit_code).toBe(1);
 expect(refusedPackage.log).toContain("Precision 0.895 < 0.90");
 for(const sample of state.samples.slice(0,21))await page.getByRole("button",{name:"Accept image "+sample.row_id,exact:true}).click();
 await expect(page.getByRole("button",{name:"Submit 200 verdicts"})).toBeEnabled();
 await page.getByRole("button",{name:"Submit 200 verdicts"}).click();
 await expect(page.getByText("Review recorded. CLI quality gate passed.")).toBeVisible();
 await page.reload();
 await expect(page.getByRole("button",{name:"Continue to package"})).toBeVisible();
 const persistedReview=await(await request.get("/api/batches/"+batch)).json();
 expect(persistedReview.samples).toHaveLength(200);
 expect(persistedReview.samples.every((sample:{verdict:string})=>sample.verdict==="accept")).toBe(true);
 expect(persistedReview.qa_passed).toBe(true);
 await page.getByRole("button",{name:"Continue to package"}).click();
 await page.getByRole("button",{name:"Package dataset",exact:true}).click();
 await expect(page.getByText("200 rows packaged")).toBeVisible({timeout:60000});
 const downloadPromise=page.waitForEvent("download");
 await page.getByRole("link",{name:"Manifest CSV",exact:true}).click();
 const download=await downloadPromise;expect(download.suggestedFilename()).toBe("manifest.csv");
 const detail=await(await request.get("/api/batches/"+batch)).json();
 const rejectedPrice=await request.post("/api/price",{data:{package:detail.packages[0].id,price:19.99}});
 expect(rejectedPrice.status()).toBe(400);
 const evidence=inspectPipeline(batch,detail.packages[0].id);
 const repo=path.resolve(process.cwd(),"..");
 mkdirSync(path.join(repo,"work"),{recursive:true});
 writeFileSync(path.join(repo,process.env.FOUNDRY_TEST_REMOTE==="1"?"work/phase6-remote-pipeline-evidence.json":"work/phase6-pipeline-evidence.json"),JSON.stringify({...evidence,recorded_at:new Date().toISOString(),price_rejection_status:rejectedPrice.status()},null,2)+"\n");
 const zipped=await request.get("/api/asset?kind=images&package="+detail.packages[0].id);
 expect(zipped.status()).toBe(200);expect(zipped.headers()["content-type"]).toBe("application/zip");
 expect((await zipped.body()).subarray(0,2).toString()).toBe("PK");
 await page.goto("/batches/"+batch);
 await page.getByLabel("Search manifest").fill(state.samples[0].row_id);
 await expect(page.locator(".manifest-table tbody tr")).toHaveCount(1);
 await expect(page.locator(".manifest-table .rights-cell")).toContainText(/CC0|platform_public_as_is/);
 await expect(page.locator(".manifest-table .attribution-cell")).toContainText("synthetic");
 await page.goto("/datasets");
 await expect(page.getByRole("heading",{name:prompt})).toBeVisible();
 await expect(page.getByText("Synthetic fixture · demonstration package only, not for sale.").first()).toBeVisible();
 await page.goto("/analytics");
 await expect(page.getByText("CLIP score distribution",{exact:true})).toBeVisible();
 await page.goto("/");
 await expect(page.getByRole("heading",{name:"Your data, refined."})).toBeVisible();
 await expect(page.getByText(prompt,{exact:true}).first()).toBeVisible();
 await page.screenshot({path:"/tmp/foundry-overview-desktop.png",fullPage:true});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:"/tmp/foundry-overview-mobile.png",fullPage:true});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
 await page.getByRole("button",{name:"Toggle navigation"}).click();
 await page.getByRole("link",{name:"Dataset catalog",exact:true}).click();
 await expect(page.getByRole("heading",{name:"Data with a paper trail."})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
 expect(errors).toEqual([]);
});

test("invalid uploads, traversal and cross-origin mutations are refused",async({request})=>{
 const bad=await request.post("/api/plan",{multipart:{prompt:"x"}});
 expect(bad.status()).toBe(400);
 const cross=await request.post("/api/price",{headers:{Origin:"https://unrelated.example"},data:{package:"test",price:10}});
 expect(cross.status()).toBe(400);
 const asset=await request.get("/api/asset?kind=images&package=..%2Fsecret");
 expect(asset.status()).toBe(400);
});

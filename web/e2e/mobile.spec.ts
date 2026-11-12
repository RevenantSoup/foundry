import {test,expect} from "@playwright/test";
import {execFileSync} from "node:child_process";
import path from "node:path";
let demos:{batch_id:string;dataset_id:string}[];
test.beforeAll(()=>{
 const repo=path.resolve(process.cwd(),"..");
 demos=JSON.parse(execFileSync(process.env.FOUNDRY_PYTHON||path.join(repo,".venv/bin/python"),[path.join(repo,"scripts/seed-demo.py"),"--root",path.join(repo,"work/web-test-data")],{encoding:"utf8"}));
});
test("390px dashboard, wizard, QA, public catalog and detail remain usable",async({page})=>{
 const errors:string[]=[];page.on("pageerror",error=>errors.push(error.message));
 await page.request.post("/api/auth/login",{data:{user:process.env.FOUNDRY_ADMIN_USER,password:process.env.FOUNDRY_ADMIN_PASSWORD}});
 await page.addInitScript(()=>localStorage.setItem("foundry-tour-v1-dismissed","true"));
 await page.setViewportSize({width:390,height:844});
 for(const url of ["/","/new","/batches/"+demos[0].batch_id+"/qa","/datasets","/datasets/"+demos[0].dataset_id]){
  await page.goto(url);await page.getByRole("heading",{level:1}).waitFor();
  if(url.endsWith("/qa"))await expect(page.locator(".crop-card")).toHaveCount(200);
  await expect(page.locator(".loading")).toHaveCount(0);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),url).toBe(true);
 }
 await page.context().clearCookies();await page.goto("/datasets");
 await expect(page.getByText("DEMO DATASETS · SYNTHETIC · NOT FOR SALE",{exact:true})).toBeVisible();
 await expect(page.getByRole("button",{name:"Save price",exact:true})).toHaveCount(0);
 await page.goto("/datasets/"+demos[0].dataset_id);
 await expect(page.getByRole("heading",{level:1})).toBeVisible();
 await expect(page.getByLabel("Owner listing price · USD",{exact:true})).toHaveCount(0);
 expect(errors).toEqual([]);
});

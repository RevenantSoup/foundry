import {test,expect} from "@playwright/test";
test("missing actual Python bridge fails promptly without a spinner or misleading success",async({page,request})=>{
 const health=await request.get("/api/health");expect(health.status()).toBe(503);expect(await health.json()).toMatchObject({db:"error",error:"database_unavailable"});
 expect((await request.get("/api/v1/datasets")).status()).toBe(401);
 expect((await request.post("/api/v1/checkout",{data:{}})).status()).toBe(401);
 expect((await request.get("/api/v1/orders/unknown")).status()).toBe(401);
 expect((await request.post("/api/v1/webhooks/stripe",{data:{}})).status()).toBe(400);
 expect((await request.get("/api/state")).status()).toBe(401);
 expect((await request.get("/api/v1/downloads?token=unknown")).status()).toBe(403);
 for(const url of ["/api/datasets","/api/datasets/unknown"]){
  const response=await request.get(url);expect(response.status()).toBe(503);
  const text=await response.text();expect(text).toContain("database_unavailable");expect(text).not.toMatch(/ENOENT|phase6-python|Traceback/);
 }
 await page.request.post("/api/auth/login",{data:{user:process.env.FOUNDRY_ADMIN_USER,password:process.env.FOUNDRY_ADMIN_PASSWORD}});
 await page.addInitScript(()=>localStorage.setItem("foundry-tour-v1-dismissed","true"));
 for(const url of ["/dashboard","/datasets","/analytics","/batches","/batches/unknown","/batches/unknown/qa","/new?batch=unknown"]){
  await page.goto(url);await expect(page.locator(".error-box").first()).toContainText("Workspace unavailable");
  await expect(page.getByLabel("Loading workspace")).toHaveCount(0);
  if(url==="/datasets")await expect(page.getByText("No private packages.",{exact:false})).toHaveCount(0);
  await page.getByRole("button",{name:"Retry",exact:true}).first().click();
  await expect(page.locator(".error-box").first()).toContainText("Workspace unavailable");
 }
});

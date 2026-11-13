import {test,expect} from "@playwright/test";
const credentials=()=>({user:process.env.FOUNDRY_ADMIN_USER,password:process.env.FOUNDRY_ADMIN_PASSWORD});
test("login failure and network failure permit retry; session survives refresh and logout",async({page})=>{
 await page.goto("/login");
 await page.getByLabel("Username",{exact:true}).fill(credentials().user!);
 await page.getByLabel("Password",{exact:true}).fill("incorrect-password");
 await page.getByRole("button",{name:"Sign in",exact:true}).click();
 await expect(page.locator(".error-box")).toContainText("Invalid username or password");
 await expect(page.getByRole("button",{name:"Sign in",exact:true})).toBeEnabled();
 await page.route("**/api/auth/login",route=>route.abort());
 await page.getByRole("button",{name:"Sign in",exact:true}).click();
 await expect(page.locator(".error-box")).toContainText(/connect|fetch|network/i);
 await expect(page.getByRole("button",{name:"Sign in",exact:true})).toBeEnabled();
 await page.unroute("**/api/auth/login");
 await page.getByLabel("Password",{exact:true}).fill(credentials().password!);
 await page.getByRole("button",{name:"Sign in",exact:true}).click();
 await expect(page).toHaveURL(/\/dashboard$/);
 await expect(page.getByRole("button",{name:"Sign out"})).toBeVisible();
 await page.reload();await expect(page.getByRole("button",{name:"Sign out"})).toBeVisible();
 await page.goto("/login");await expect(page).toHaveURL(/\/dashboard$/);
 await page.getByRole("button",{name:"Sign out"}).click();await expect(page).toHaveURL(/\/login$/);
 await page.goto("/dashboard");await expect(page).toHaveURL(/\/login\?next=/);
});
test("workspace failures stop loading and retry recovers",async({page})=>{
 await page.request.post("/api/auth/login",{data:credentials()});
 await page.addInitScript(()=>localStorage.setItem("foundry-tour-v1-dismissed","true"));
 await page.route("**/api/state",route=>route.fulfill({status:503,json:{error:"database_unavailable",message:"Dataset store unavailable"}}));
 for(const url of ["/dashboard","/analytics","/batches"]){
  await page.goto(url);await expect(page.locator(".error-box").first()).toContainText(/Workspace unavailable/);
  await expect(page.getByLabel("Loading workspace")).toHaveCount(0);
  await expect(page.getByRole("button",{name:"Retry",exact:true}).first()).toBeVisible();
 }
 await page.unroute("**/api/state");
 await page.getByRole("button",{name:"Retry",exact:true}).first().click();
 await expect(page.getByRole("heading",{name:"Every batch, in view."})).toBeVisible();
 await expect(page.locator(".error-box")).toHaveCount(0);
});
test("catalog malformed HTTP and hanging requests terminate with retry",async({page})=>{
 await page.route("**/api/datasets?*",route=>route.fulfill({status:500,json:{error:"unexpected_error",message:"Could not load datasets"}}));
 await page.goto("/datasets");await expect(page.locator(".error-box").first()).toContainText("Could not load datasets");
 await expect(page.getByLabel("Loading workspace")).toHaveCount(0);
 await page.unroute("**/api/datasets?*");
 await page.route("**/api/datasets?*",route=>route.fulfill({status:200,body:"not-json",contentType:"application/json"}));
 await page.getByRole("button",{name:"Retry",exact:true}).first().click();
 await expect(page.locator(".error-box").first()).toContainText(/invalid response/i);
 await page.unroute("**/api/datasets?*");
 await page.route("**/api/datasets?*",()=>{});
 await page.getByRole("button",{name:"Retry",exact:true}).first().click();
 await expect(page.locator(".error-box").first()).toContainText(/timed out/i,{timeout:15000});
 await expect(page.getByLabel("Loading workspace")).toHaveCount(0);
 await page.unroute("**/api/datasets?*");
 await page.getByRole("button",{name:"Retry",exact:true}).first().click();
 await expect(page.getByText("Filters combine and are evaluated in SQLite")).toBeVisible();
 await expect(page.locator(".error-box")).toHaveCount(0);
});
test("successful empty workspace remains visible during a failed background refresh",async({page,request})=>{
 await page.request.post("/api/auth/login",{data:credentials()});
 await page.addInitScript(()=>localStorage.setItem("foundry-tour-v1-dismissed","true"));
 const response=await request.post("/api/auth/login",{data:credentials()});expect(response.ok()).toBe(true);
 const state=await(await request.get("/api/state")).json();
 state.batches=[];state.packages=[];state.sources=[];state.licences=[];
 state.totals={...state.totals,batches:0,harvested:0,shortlisted:0,verified:0,packaged:0,precision:null};
 let calls=0;
 await page.route("**/api/state",route=>{calls++;return calls===1?route.fulfill({json:state}):route.fulfill({status:500,json:{error:"request_failed",message:"Temporary refresh failure"}})});
 await page.goto("/dashboard");
 await expect(page.getByText("Your next dataset starts here")).toBeVisible();
 await expect(page.locator(".error-box")).toContainText("Temporary refresh failure",{timeout:10000});
 await expect(page.getByText("Your next dataset starts here")).toBeVisible();
 await expect(page.getByLabel("Loading workspace")).toHaveCount(0);
 expect(calls).toBe(2);
});
test("authenticated login visits restore the session and reject unsafe return destinations",async({page})=>{
 await page.request.post("/api/auth/login",{data:credentials()});
 for(const next of ["//example.com","/\\example.com","https://example.com","/login"]){
  const tab=await page.context().newPage();await tab.goto("/login?next="+encodeURIComponent(next),{waitUntil:"commit"});await expect(tab).toHaveURL(/\/dashboard$/);await expect(tab.getByRole("heading",{name:"Your data, refined."})).toBeVisible();await tab.close();
 }
 await page.goto("/login?next=%2Fdashboard&next=%2Fbatches",{waitUntil:"commit"});await expect(page).toHaveURL(/\/dashboard$/);await expect(page.getByRole("heading",{name:"Your data, refined."})).toBeVisible();
 await page.goto("/login?next=%2Fbatches",{waitUntil:"commit"});await expect(page).toHaveURL(/\/batches$/);
});

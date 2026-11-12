import {test,expect} from "@playwright/test";
test("dashboard login redirect, valid session, logout and public scope",async({page,request})=>{
 const response=await request.get("/",{maxRedirects:0});expect(response.status()).toBe(307);expect(response.headers().location).toContain("/login");
 expect((await request.get("/api/state")).status()).toBe(401);
 expect((await request.get("/api/v1/datasets")).status()).toBe(401);
 expect((await request.get("/datasets")).status()).toBe(200);
 await page.goto("/");await expect(page).toHaveURL(/\/login/);
 await page.getByLabel("Username",{exact:true}).fill(process.env.FOUNDRY_ADMIN_USER!);
 await page.getByLabel("Password",{exact:true}).fill(process.env.FOUNDRY_ADMIN_PASSWORD!);
 await page.getByRole("button",{name:"Sign in",exact:true}).click();await expect(page).toHaveURL("/");
 await expect(page.getByRole("heading",{name:"Your data, refined."})).toBeVisible();
 const cookies=await page.context().cookies();expect(cookies.find(c=>c.name==="foundry_admin")?.httpOnly).toBe(true);
 await page.request.post("/api/auth/logout");
 await page.goto("/");await expect(page).toHaveURL(/\/login/);
});

test("health, public metadata and dismissible guided tour",async({page,request})=>{
 const health=await request.get("/api/health");expect(health.status()).toBe(200);expect(await health.json()).toMatchObject({status:"ok",db:"ok"});
 await page.request.post("/api/auth/login",{data:{user:process.env.FOUNDRY_ADMIN_USER,password:process.env.FOUNDRY_ADMIN_PASSWORD}});
 await page.goto("/");await page.getByRole("button",{name:"Take the tour",exact:true}).click();
 await expect(page.getByRole("dialog")).toBeVisible();
 await page.keyboard.press("Escape");await expect(page.getByRole("dialog")).not.toBeVisible();
 await page.reload();await expect(page.getByRole("button",{name:"Take the tour",exact:true})).toHaveCount(0);
 expect((await request.get("/robots.txt")).status()).toBe(200);
 expect((await request.get("/sitemap.xml")).status()).toBe(200);
});

test("ambiguous asset queries cannot bypass owner login",async({request})=>{
 const response=await request.get("/api/asset?kind=sample&kind=images&package=private");
 expect(response.status()).toBe(401);
 const manifest=await request.get("/api/asset?kind=sample&kind=manifest&package=private");
 expect(manifest.status()).toBe(401);
});

test("malformed origins return a consistent forbidden response",async({request})=>{
 const response=await request.post("/api/auth/login",{headers:{Origin:"not-a-valid-origin"},data:{}});
 expect(response.status()).toBe(403);
 expect(await response.json()).toMatchObject({error:"forbidden",message:expect.any(String)});
});

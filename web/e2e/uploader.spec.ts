import {test,expect} from "@playwright/test";
const png=Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII=","base64");
const image=(name:string)=>({name,mimeType:"image/png",buffer:png});
test.beforeEach(async({page})=>{
 await page.request.post("/api/auth/login",{data:{user:process.env.FOUNDRY_ADMIN_USER,password:process.env.FOUNDRY_ADMIN_PASSWORD}});
 await page.addInitScript(()=>{
  localStorage.setItem("foundry-tour-v1-dismissed","true");
  const tracked={created:[] as string[],revoked:[] as string[]};Object.assign(window,{uploaderURLs:tracked});
  const create=URL.createObjectURL.bind(URL),revoke=URL.revokeObjectURL.bind(URL);
  URL.createObjectURL=blob=>{const url=create(blob);tracked.created.push(url);return url};
  URL.revokeObjectURL=url=>{tracked.revoked.push(url);revoke(url)};
 });
 await page.goto("/new");await expect(page.getByLabel("Reference images",{exact:true})).toBeEnabled();
});
test("sequential additions, drag/drop, limits, remove, replace and local originals",async({page})=>{
 const upload=page.getByLabel("Reference images",{exact:true});
 await page.getByLabel("Image specification").fill("People wearing safety glasses");
 await upload.setInputFiles([image("one.png"),image("two.png")]);
 await upload.setInputFiles([image("three.png"),image("four.png")]);
 await expect(page.getByText("4 / 6 selected")).toBeVisible();
 await page.locator(".upload-zone").evaluate((element,bytes)=>{
  const transfer=new DataTransfer();for(const name of ["five.png","six.png","seven.png"])transfer.items.add(new File([new Uint8Array(bytes)],name,{type:"image/png",lastModified:123}));
  element.dispatchEvent(new DragEvent("drop",{bubbles:true,dataTransfer:transfer}));
 },Array.from(png));
 await expect(page.getByText("6 / 6 selected")).toBeVisible();
 await expect(page.getByText(/Only six reference images/)).toBeVisible();
 await expect(page.getByRole("img",{name:"Reference 1: one.png",exact:true})).toBeVisible();
 await expect(page.getByText("seven.png",{exact:true})).toHaveCount(0);
 for(const width of [375,768,1280]){await page.setViewportSize({width,height:900});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);await expect(page.getByRole("button",{name:"Remove reference 2",exact:true})).toBeVisible()}
 await page.getByRole("button",{name:"Remove reference 2",exact:true}).click();
 await expect(page.getByText("5 / 6 selected")).toBeVisible();
 await expect(page.getByRole("button",{name:"Generate plan"})).toBeDisabled();
 await upload.setInputFiles(image("two.png"));
 await page.getByLabel("Replace reference 1",{exact:true}).setInputFiles(image("replacement.png"));
 await expect(page.getByRole("img",{name:"Reference 1: replacement.png",exact:true})).toBeVisible();
 expect(await upload.inputValue()).toBe("");
 const urls=await page.evaluate(()=>(window as unknown as {uploaderURLs:{created:string[];revoked:string[]}}).uploaderURLs);
 expect(urls.created.length-urls.revoked.length).toBe(6);expect(urls.revoked.length).toBeGreaterThanOrEqual(2);
 await page.route("**/api/runtime",route=>route.fulfill({json:{remote:false}}));
 let submitted:string[]=[];
 await page.route("**/api/plan",async route=>{
  const request=route.request();const body=request.postDataBuffer()!;
  const form=await new Response(new Uint8Array(body),{headers:{"Content-Type":request.headers()["content-type"]}}).formData();
  const refs=form.getAll("refs") as File[];submitted=refs.map(file=>file.name);
  for(const file of refs)expect(Buffer.from(await file.arrayBuffer())).toEqual(png);
  await route.fulfill({status:400,json:{message:"Upload verified"}});
 });
 await page.getByRole("button",{name:"Generate plan"}).click();
 await expect.poll(()=>submitted.length).toBe(6);
 expect(submitted).toEqual(["replacement.png","three.png","four.png","five.png","six.png","two.png"]);
});
test("rejects duplicate, non-image and oversized files without changing selection",async({page})=>{
 const upload=page.getByLabel("Reference images",{exact:true});
 async function drop(lastModified:number){await page.locator(".upload-zone").evaluate((element,date)=>{const transfer=new DataTransfer();transfer.items.add(new File([new Uint8Array([1])],"same.png",{type:"image/png",lastModified:date}));element.dispatchEvent(new DragEvent("drop",{bubbles:true,dataTransfer:transfer}))},lastModified)}
 await drop(123);await drop(123);
 await expect(page.getByText(/already selected/)).toBeVisible();
 await expect(page.getByText("1 / 6 selected")).toBeVisible();
 await drop(124);await expect(page.getByText("2 / 6 selected")).toBeVisible();
 await upload.setInputFiles({name:"text.txt",mimeType:"text/plain",buffer:Buffer.from("no")});
 await expect(page.getByText(/choose an image file/)).toBeVisible();
 await upload.setInputFiles({name:"large.png",mimeType:"image/png",buffer:Buffer.alloc(10*1024*1024+1)});
 await expect(page.getByText(/images must be 10 MB or smaller/)).toBeVisible();
 await expect(page.getByText("2 / 6 selected")).toBeVisible();
 await page.getByLabel("Replace reference 1",{exact:true}).setInputFiles({name:"bad.txt",mimeType:"text/plain",buffer:Buffer.from("bad")});
 await expect(page.getByRole("img",{name:"Reference 1: same.png",exact:true})).toHaveCount(1);
});

test("fewer than six references explains the requirement and cannot submit",async({page})=>{
 await page.getByLabel("Image specification").fill("People wearing safety glasses");
 await page.getByLabel("Reference images",{exact:true}).setInputFiles(image("only.png"));
 await expect(page.getByText("Select exactly six distinct images to generate a plan.",{exact:false})).toBeVisible();
 await expect(page.getByRole("button",{name:"Generate plan"})).toBeDisabled();
 let requests=0;page.on("request",r=>{if(r.url().endsWith("/api/plan"))requests++});
 await page.locator("form").evaluate(form=>(form as HTMLFormElement).requestSubmit());
 await expect(page.locator(".error-box")).toContainText("Upload exactly six reference images");expect(requests).toBe(0);
});

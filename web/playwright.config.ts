import {defineConfig} from "@playwright/test";
import path from "node:path";
import {randomBytes} from "node:crypto";
process.env.FOUNDRY_ADMIN_USER||="test-admin";
process.env.FOUNDRY_ADMIN_PASSWORD||=randomBytes(20).toString("hex");
process.env.FOUNDRY_SESSION_SECRET||=randomBytes(32).toString("hex");
export default defineConfig({
 testDir:"./e2e",testIgnore:["**/payments.spec.ts"],fullyParallel:false,workers:1,timeout:300000,
 expect:{timeout:20000},reporter:"list",
 use:{baseURL:"http://127.0.0.1:3100",viewport:{width:1440,height:1050},trace:"retain-on-failure",actionTimeout:15000,navigationTimeout:30000},
 webServer:{command:"npm run dev -- --port 3100",url:"http://127.0.0.1:3100",reuseExistingServer:false,timeout:120000,env:{FOUNDRY_ROOT:path.resolve(process.cwd(),"../work/web-test-data"),NEXT_TELEMETRY_DISABLED:"1",FOUNDRY_ADMIN_USER:process.env.FOUNDRY_ADMIN_USER,FOUNDRY_ADMIN_PASSWORD:process.env.FOUNDRY_ADMIN_PASSWORD,FOUNDRY_SESSION_SECRET:process.env.FOUNDRY_SESSION_SECRET}},
});

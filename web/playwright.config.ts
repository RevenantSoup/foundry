import {defineConfig} from "@playwright/test";
import path from "node:path";
export default defineConfig({
 testDir:"./e2e",fullyParallel:false,workers:1,timeout:300000,
 expect:{timeout:20000},reporter:"list",
 use:{baseURL:"http://127.0.0.1:3100",viewport:{width:1440,height:1050},trace:"retain-on-failure",actionTimeout:15000,navigationTimeout:30000},
 webServer:{command:"npm run dev -- --port 3100",url:"http://127.0.0.1:3100",reuseExistingServer:false,timeout:120000,env:{FOUNDRY_ROOT:path.resolve(process.cwd(),"../work/web-test-data"),NEXT_TELEMETRY_DISABLED:"1"}},
});

import {defineConfig} from "@playwright/test";
import {randomBytes} from "node:crypto";
import path from "node:path";
const repo=path.resolve(process.cwd(),"..");const python=process.env.FOUNDRY_PYTHON||path.join(repo,".venv/bin/python");
const remote=process.env.FOUNDRY_TEST_REMOTE==="1";const port=remote?3200:3300;
for(const name of ["FOUNDRY_ADMIN_PASSWORD","FOUNDRY_SESSION_SECRET","FOUNDRY_WORKER_API_KEY","FOUNDRY_DOWNLOAD_SECRET"])process.env[name]||=randomBytes(32).toString("hex");
process.env.FOUNDRY_ADMIN_USER||="test-admin";
for(const [name,prefix] of [["STRIPE_SECRET_KEY","sk_test_"],["STRIPE_PUBLISHABLE_KEY","pk_test_"],["STRIPE_WEBHOOK_SECRET","whsec_"]])process.env[name]||=prefix+randomBytes(24).toString("hex");
const paymentEnv=Object.fromEntries(["STRIPE_SECRET_KEY","STRIPE_PUBLISHABLE_KEY","STRIPE_WEBHOOK_SECRET","FOUNDRY_DOWNLOAD_SECRET","FOUNDRY_WORKER_API_KEY","FOUNDRY_ADMIN_USER","FOUNDRY_ADMIN_PASSWORD","FOUNDRY_SESSION_SECRET"].map(key=>[key,process.env[key]!]));
const root=path.join(repo,"work/web-test-data");const common={...paymentEnv,STRIPE_SUCCESS_URL:`http://127.0.0.1:${port}/checkout/success?order={ORDER_ID}&session_id={CHECKOUT_SESSION_ID}`,STRIPE_CANCEL_URL:`http://127.0.0.1:${port}/checkout/cancel`,FOUNDRY_ROOT:root};
const shell=(s:string)=>"'"+s.replaceAll("'","'\\''")+"'";
export default defineConfig({testDir:"./e2e",testMatch:remote?["payments.spec.ts","workflow.spec.ts"]:["payments.spec.ts"],workers:1,timeout:300000,expect:{timeout:30000},reporter:"list",use:{baseURL:`http://127.0.0.1:${port}`,viewport:{width:1440,height:1050},trace:"retain-on-failure"},webServer:[
 ...(remote?[{command:shell(python)+" e2e/serve-phase5-worker.py",url:"http://127.0.0.1:8100/health",timeout:120000,env:common}]:[]),
 {command:`npm run dev -- --port ${port}`,url:`http://127.0.0.1:${port}`,timeout:120000,env:{...common,NEXT_TELEMETRY_DISABLED:"1",FOUNDRY_WORKER_URL:remote?"http://127.0.0.1:8100":"",FOUNDRY_ROOT:remote?"/nonexistent-vercel-storage":root,FOUNDRY_PYTHON:remote?"/nonexistent-vercel-python":path.join(repo,"web/e2e/mock-stripe-python.sh"),FOUNDRY_TEST_PYTHON:python,...(remote?{STRIPE_SECRET_KEY:"",STRIPE_PUBLISHABLE_KEY:"",STRIPE_WEBHOOK_SECRET:"",FOUNDRY_DOWNLOAD_SECRET:""}:{})}}
]});

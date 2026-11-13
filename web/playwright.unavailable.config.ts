import config from "./playwright.config";
import path from "node:path";
const server=config.webServer;
if(!server||Array.isArray(server))throw new Error("Expected one local test server");
const unavailableConfig={...config,testIgnore:[],testMatch:["unavailable.spec.ts"],webServer:{...server,env:{...server.env,FOUNDRY_PYTHON:"/missing/phase6-python",FOUNDRY_WORKER_URL:"",FOUNDRY_ROOT:path.resolve(process.cwd(),"../work/unavailable-test-data")}}};
export default unavailableConfig;

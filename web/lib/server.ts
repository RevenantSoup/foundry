import "server-only";
import {spawn} from "node:child_process";
import {promises as fs, existsSync} from "node:fs";
import path from "node:path";
import {randomUUID} from "node:crypto";
import type {Job} from "./types";

export const repo = path.resolve(process.cwd(), "..");
const configured = path.resolve(process.env.FOUNDRY_ROOT || path.join(repo,"data"));
export const dataRoot = existsSync(path.join(configured,"pyproject.toml")) ? path.join(configured,"data") : configured;
export const python = process.env.FOUNDRY_PYTHON || (existsSync(path.join(repo,".venv/bin/python")) ? path.join(repo,".venv/bin/python") : "python3");
const bridgePath = path.join(repo,"web/bridge.py");
export function validId(id:string) {if(!/^[a-zA-Z0-9_-]{1,100}$/.test(id)) throw new Error("Invalid identifier");return id;}
const env = () => ({...process.env,FOUNDRY_ROOT:dataRoot,PYTHONPATH:repo});
export async function bridge<T>(mode:string,body:object={}):Promise<T> {
  return new Promise((resolve,reject)=>{
    const child=spawn(python,[bridgePath,mode],{cwd:repo,env:env(),stdio:["pipe","pipe","pipe"]});
    let output="",errors="";let settled=false;
    const timeout=setTimeout(()=>{child.kill();reject(new Error("Backend request timed out"));},120000);
    child.stdout.on("data",chunk=>{output+=chunk.toString()});
    child.stderr.on("data",chunk=>{errors+=chunk.toString()});
    child.on("error",error=>{clearTimeout(timeout);settled=true;reject(new Error("Python bridge unavailable: "+error.message))});
    child.on("close",code=>{
      clearTimeout(timeout); if(settled)return;
      try {const result=JSON.parse(output); if(code!==0||result.error)reject(new Error(result.error||errors||"Backend failed"));else resolve(result);}
      catch {reject(new Error(errors||output||"Invalid backend response"))}
    });
    child.stdin.end(JSON.stringify(body));
  });
}
export async function startJob(batch:string,action:string,payload:object) {
  validId(batch);
  if(!["harvest","filter","qa","review","package"].includes(action)) throw new Error("Unknown action");
  await bridge("batch",{batch});
  const id=randomUUID(); const directory=path.join(dataRoot,"web/jobs");
  await fs.mkdir(directory,{recursive:true});
  const job:Job={id,batch,action,status:"queued",log:""};
  await fs.writeFile(path.join(directory,id+".json"),JSON.stringify({...job,payload}));
  const child=spawn(python,[bridgePath,"job",id],{cwd:repo,env:env(),detached:true,stdio:"ignore"});
  child.on("error",async error=>{await fs.writeFile(path.join(directory,id+".json"),JSON.stringify({...job,status:"failed",exit_code:1,log:error.message}))});
  child.unref();
  return job;
}
export async function jobStatus(id:string):Promise<Job> {
  const file=path.join(dataRoot,"web/jobs",validId(id)+".json");
  const job=JSON.parse(await fs.readFile(file,"utf8"));
  if(job.status==="running" && job.pid) {
    try {process.kill(job.pid,0)} catch {job.status="failed";job.exit_code=1;job.log+="\nWorker stopped unexpectedly. Retry the stage to resume.";}
  }
  const {payload:_,...publicJob}=job;
  void _;
  return publicJob;
}

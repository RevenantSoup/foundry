import {spawnSync} from "node:child_process";
import {existsSync} from "node:fs";
import path from "node:path";
const repo=path.resolve(process.cwd(),"..");
const python=process.env.FOUNDRY_PYTHON || (existsSync(path.join(repo,".venv/bin/python"))?path.join(repo,".venv/bin/python"):"python3");
const result=spawnSync(python,[path.join(repo,"web/bridge.py"),"seed"],{stdio:"inherit",env:{...process.env,PYTHONPATH:repo},cwd:repo});
process.exit(result.status??1);

"""Local-only JSON bridge. All mutations execute the existing Foundry CLI."""
from __future__ import annotations
import csv
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time
import uuid
import zipfile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def root():
    configured = Path(os.environ.get("FOUNDRY_ROOT", REPO / "data")).resolve()
    return configured / "data" if (configured / "pyproject.toml").is_file() else configured


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", value):
        raise ValueError("Invalid identifier")
    return value


def atomic(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(payload))
    temporary.replace(path)


def connection():
    path = root() / "foundry.sqlite3"
    if not path.exists():
        return None
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=30)
    db.row_factory = sqlite3.Row
    return db


def sale_clearance(licences):
    return bool(licences) and set(licences) <= {"CC0", "CC-BY", "CC-BY-SA"}


def read_packages():
    prices_path = root() / "web" / "prices.json"
    prices = json.loads(prices_path.read_text()) if prices_path.exists() else {}
    packages = []
    for manifest in sorted((root() / "packages").glob("*/manifest.csv")):
        try:
            with manifest.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            if not rows or any(not r.get("licence", "").strip() or not r.get("attribution", "").strip() for r in rows):
                continue
            licences = sorted({r["licence"] for r in rows})
            meta = json.loads((manifest.parent / "dataset.json").read_text())
            packages.append({
                "id": manifest.parent.name, "batch_id": meta["batch_id"],
                "version": meta["version"], "count": len(rows), "licences": licences,
                "attributions": sorted({r["attribution"] for r in rows}),
                "train": sum(r["split"] == "train" for r in rows),
                "validation": sum(r["split"] == "validation" for r in rows),
                "provenance_hash": hashlib.sha256("".join(r["provenance_hash"] for r in rows).encode()).hexdigest(),
                "price": prices.get(manifest.parent.name, 0),
                "sale_cleared": sale_clearance(licences),
                "synthetic": all(r["source_url"].startswith("stub://") for r in rows),
            })
        except (ValueError, KeyError, OSError):
            continue
    return packages


def snapshot():
    db = connection()
    rows, batches, quota = [], [], []
    packages = read_packages()
    if db:
        try:
            rows = [dict(r) for r in db.execute("SELECT * FROM rows")]
            for record in db.execute("SELECT * FROM batches ORDER BY rowid DESC"):
                plan = json.loads(record["plan"])
                items = [r for r in rows if r["batch_id"] == record["id"]]
                samples = [dict(r) for r in db.execute("SELECT * FROM qa_samples WHERE batch_id=?", (record["id"],))]
                reviewed = [r for r in samples if r["verdict"] in ("accept", "reject")]
                precision = sum(r["verdict"] == "accept" for r in reviewed) / len(reviewed) if reviewed else None
                exported = [p for p in packages if p["batch_id"] == record["id"]]
                shortlisted = sum(r["vlm_verdict"] in ("accept", "reject") for r in items)
                status = "Packaged" if exported else "QA passed" if record["qa_passed"] else "Review" if samples else "Filtered" if shortlisted else "Harvested" if items else "Planned"
                batches.append({
                    "id": record["id"], "prompt": plan["prompt"], "plan": plan,
                    "synthetic": plan.get("offline", True), "status": status,
                    "harvested": len(items), "shortlisted": shortlisted,
                    "verified": sum(r["vlm_verdict"] == "accept" for r in items),
                    "packaged": exported[-1]["count"] if exported else 0,
                    "qa_precision": precision, "reviewed": len(reviewed),
                    "qa_passed": bool(record["qa_passed"]),
                    "licences": sorted({r["licence"] for r in items}),
                    "sources": sorted({r["source"] for r in items}),
                    "created_at": min((r["captured_at"] for r in items), default=None),
                })
            quota = [dict(r) for r in db.execute("SELECT * FROM quota ORDER BY day")]
        finally:
            db.close()
    def mix(key):
        result = {}
        for row in rows:
            result[row[key]] = result.get(row[key], 0) + 1
        return [{"name": key, "value": value} for key, value in result.items()]
    distribution = [{"name": f"{i/10:.1f}–{(i+1)/10:.1f}", "value": 0} for i in range(10)]
    for row in rows:
        if row["clip_score"] is not None:
            distribution[min(9, max(0, int(row["clip_score"] * 10)))]["value"] += 1
    precision = [b["qa_precision"] for b in batches if b["qa_precision"] is not None]
    totals = {key: sum(b[key] for b in batches) for key in ("harvested", "shortlisted", "verified", "packaged")}
    totals.update(batches=len(batches), precision=sum(precision)/len(precision) if precision else None)
    for package in packages:
        batch = next((b for b in batches if b["id"] == package["batch_id"]), None)
        package["prompt"] = batch["prompt"] if batch else package["batch_id"]
    embeddings = root() / "embeddings.npy"
    return {"batches": batches, "totals": totals, "sources": mix("source"), "licences": mix("licence"),
            "quota": quota, "distribution": distribution, "packages": packages,
            "embedding_bytes": embeddings.stat().st_size if embeddings.exists() else 0}


def batch_detail(batch):
    identifier(batch)
    state = snapshot()
    record = next((b for b in state["batches"] if b["id"] == batch), None)
    if not record:
        raise ValueError("Unknown batch")
    db = connection()
    try:
        record["rows"] = [dict(r) for r in db.execute("SELECT * FROM rows WHERE batch_id=? ORDER BY clip_score DESC, id", (batch,))]
        record["samples"] = [dict(r) for r in db.execute("SELECT * FROM qa_samples WHERE batch_id=? ORDER BY position", (batch,))]
        record["drops"] = [dict(r) for r in db.execute("SELECT reason,count(*) AS count FROM drops WHERE batch_id=? GROUP BY reason", (batch,))]
    finally:
        db.close()
    record["packages"] = [p for p in state["packages"] if p["batch_id"] == batch]
    record["contact_sheet"] = (root() / "qa" / batch / "contact-sheet.png").exists()
    return record


def cli_base():
    return [sys.executable, "-u", "-m", "foundry.cli", "--root", str(root())]


def command_for(action, batch, payload):
    if action not in ("harvest", "filter", "qa", "review", "package"):
        raise ValueError("Unknown action")
    identifier(batch)
    detail = batch_detail(batch)
    command = cli_base() + [("qa" if action == "review" else action), "--batch", batch]
    if action == "harvest" and not detail["synthetic"]:
        video_dir = os.environ.get("FOUNDRY_VIDEO_DIR")
        if video_dir:
            command += ["--video-dir", video_dir]
    if action == "filter" and not detail["synthetic"]:
        command += ["--verifier", "openai"]
    if action == "review":
        verdicts = payload.get("verdicts", [])
        if len(verdicts) != 200 or any(v.get("verdict") not in ("accept", "reject") for v in verdicts):
            raise ValueError("Review all 200 images before submitting")
        if {v.get("id") for v in verdicts} != {r["row_id"] for r in detail["samples"]}:
            raise ValueError("Verdict IDs must match the current QA sample")
        path = root() / "web" / "reviews" / (uuid.uuid4().hex + ".csv")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["id", "verdict"])
            writer.writeheader()
            writer.writerows({"id": v["id"], "verdict": v["verdict"]} for v in verdicts)
        command += ["--verdicts", str(path)]
    return command


def run_job(job_id):
    identifier(job_id)
    path = root() / "web" / "jobs" / (job_id + ".json")
    job = json.loads(path.read_text())
    lock_path = root() / "web" / "pipeline.lock"
    with lock_path.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            job.update(status="failed", exit_code=1, log="Another pipeline job is running. Wait, then retry.")
            atomic(path, job)
            return
        job.update(status="running", pid=os.getpid(), started_at=time.time(), log="")
        atomic(path, job)
        try:
            command = command_for(job["action"], job["batch"], job.get("payload", {}))
            env = dict(os.environ, PYTHONPATH=str(REPO), PYTHONUNBUFFERED="1")
            with subprocess.Popen(command, cwd=REPO, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as process:
                for line in process.stdout:
                    job["log"] = (job["log"] + line)[-100000:]
                    atomic(path, job)
                code = process.wait()
            job.update(exit_code=code, status="succeeded" if code == 0 else "failed")
        except Exception as error:
            job.update(status="failed", exit_code=1, log=job["log"] + str(error))
        job["finished_at"] = time.time()
        atomic(path, job)


def make_plan(payload):
    prompt = payload.get("prompt", "").strip()
    if not prompt or len(prompt) > 4000:
        raise ValueError("Enter a prompt between 1 and 4000 characters")
    upload = identifier(payload["upload"])
    directory = root() / "web" / "refs" / upload
    target = int(payload.get("target", 200))
    threshold = float(payload.get("threshold", .28))
    if not 200 <= target <= 10000 or not -1 <= threshold <= 1:
        raise ValueError("Invalid target or threshold")
    command = cli_base() + ["plan", "--prompt", prompt, "--refs", str(directory),
                           "--target", str(target), "--threshold", str(threshold)]
    if payload.get("live"):
        command += ["--live"]
    result = subprocess.run(command, cwd=REPO, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise ValueError(result.stderr or result.stdout)
    match = re.search(r"batch_id=([a-f0-9]+)", result.stdout)
    if not match:
        raise ValueError("Planner did not return a batch ID")
    return batch_detail(match[1])


def asset(payload):
    kind = payload["kind"]
    batch = identifier(payload.get("batch", "unused"))
    if kind in ("contact", "crop"):
        detail = batch_detail(batch)
        if kind == "contact":
            path = root() / "qa" / batch / "contact-sheet.png"
        else:
            id = identifier(payload["id"])
            if id not in {r["row_id"] for r in detail["samples"]}:
                raise ValueError("Image is not part of this QA sample")
            matches = list((root() / "qa" / batch).glob("*-" + id + ".png"))
            if not matches:
                raise ValueError("Crop not found; generate QA first")
            path = matches[0]
        mime = "image/png"
    elif kind in ("manifest", "images"):
        package = identifier(payload["package"])
        if not any(p["id"] == package for p in read_packages()):
            raise ValueError("Package not found or has missing rights")
        directory = root() / "packages" / package
        if kind == "manifest":
            path, mime = directory / "manifest.csv", "text/csv"
        else:
            path = root() / "web" / "downloads" / (package + ".zip")
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                temporary = path.with_suffix("." + uuid.uuid4().hex + ".tmp")
                with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    for file in sorted(directory.rglob("*")):
                        if file.is_file():
                            archive.write(file, file.relative_to(directory))
                temporary.replace(path)
            mime = "application/zip"
    else:
        raise ValueError("Unknown asset")
    if not path.is_file():
        raise ValueError("File not found")
    if not path.resolve().is_relative_to(root()):
        raise ValueError("Invalid file path")
    return {"path": str(path), "mime": mime, "filename": path.name}


def price(payload):
    package = identifier(payload["package"])
    dataset = next((p for p in read_packages() if p["id"] == package), None)
    if not dataset or not dataset["sale_cleared"] or dataset["synthetic"]:
        raise ValueError("Only rights-cleared, non-synthetic datasets can have a listing price")
    amount = float(payload["price"])
    if not 0 <= amount <= 1000000 or not amount == amount:
        raise ValueError("Price must be between 0 and 1,000,000 USD")
    path = root() / "web" / "prices.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        prices = json.loads(path.read_text()) if path.exists() else {}
        prices[package] = round(amount, 2)
        atomic(path, prices)
    return {"price": prices[package]}


def seed():
    from PIL import Image
    directory = root() / "web" / "refs" / uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=True)
    for i in range(6):
        Image.new("RGB", (128, 128), (i * 40, 80, 120)).save(directory / f"{i}.png")
    batch = make_plan({"upload": directory.name, "prompt": "Synthetic fixture demo " + uuid.uuid4().hex[:6]})["id"]
    for action in ("harvest", "filter", "qa"):
        subprocess.run(command_for(action, batch, {}), cwd=REPO, check=True, stdout=sys.stderr)
    subprocess.run(cli_base() + ["qa", "--batch", batch, "--stub-verdicts", "accept"], cwd=REPO, check=True, stdout=sys.stderr)
    subprocess.run(command_for("package", batch, {}), cwd=REPO, check=True, stdout=sys.stderr)
    return {"batch_id": batch, "synthetic": True}


if __name__ == "__main__":
    try:
        mode = sys.argv[1]
        payload = json.loads(sys.stdin.read() or "{}") if mode not in ("job", "seed") else {}
        if mode == "job":
            run_job(sys.argv[2])
        else:
            result = {"state": snapshot, "batch": lambda: batch_detail(payload["batch"]),
                      "plan": lambda: make_plan(payload), "asset": lambda: asset(payload),
                      "price": lambda: price(payload), "seed": seed}[mode]()
            print(json.dumps(result))
    except Exception as error:
        print(json.dumps({"error": str(error)}))
        sys.exit(1)

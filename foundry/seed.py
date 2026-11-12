"""Idempotent, explicitly synthetic demos through the existing offline pipeline."""
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from PIL import Image
from .db import Database

def seed_demo(root):
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=True)
    lock_path=root/'web'/'pipeline.lock';lock_path.parent.mkdir(parents=True,exist_ok=True)
    with lock_path.open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('A pipeline is running; retry demo seeding later')
        refs=root/'demo'/'refs';refs.mkdir(parents=True,exist_ok=True)
        for i in range(6):
            path=refs/f'{i}.png'
            if not path.exists():Image.new('RGB',(128,128),(i*40,80,120)).save(path)
        db=Database(root/'foundry.sqlite3')
        base=[sys.executable,'-u','-m','foundry.cli','--root',str(root)]
        results=[]
        def call(args):
            result=subprocess.run(base+args,capture_output=True,text=True)
            if result.returncode:raise ValueError(result.stderr or result.stdout)
            if result.stderr:print(result.stderr,file=sys.stderr,end='')
            return result.stdout
        try:
            for label in ('Safety glasses','Workshop frames'):
                prompt='DEMO · '+label+' · synthetic fixture'
                batch=None
                for record in db.conn.execute('SELECT id,plan FROM batches ORDER BY rowid'):
                    plan=json.loads(record['plan'])
                    if plan.get('prompt')==prompt and plan.get('offline'):
                        batch=record['id'];break
                if batch is None:
                    output=call(['plan','--prompt',prompt,'--refs',str(refs)])
                    batch=re.search(r'batch_id=([a-f0-9]+)',output)[1]
                package=db.conn.execute('SELECT id FROM datasets WHERE batch_id=? ORDER BY created_at DESC',(batch,)).fetchone()
                if not package or not (root/'packages'/package['id']/'manifest.csv').exists():
                    for action in ('harvest','filter','qa'):call([action,'--batch',batch])
                    # Explicit fixture QA only; the CLI refuses this option for real source media.
                    call(['qa','--batch',batch,'--stub-verdicts','accept'])
                    call(['package','--batch',batch])
                    package=db.conn.execute('SELECT id FROM datasets WHERE batch_id=? ORDER BY created_at DESC',(batch,)).fetchone()
                results.append({'batch_id':batch,'dataset_id':package['id'],'synthetic':True})
        finally:db.close()
    return results

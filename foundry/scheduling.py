"""Small UTC cron scheduler. No queue; one advisory lock per schedule."""
from datetime import datetime, timezone, timedelta
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

def add_schedule(db,spec_path,interval,run_time,now=None):
    spec_path=Path(spec_path).resolve()
    spec=json.loads(spec_path.read_text())
    if not spec.get('prompt') or not spec.get('refs'):
        raise ValueError('Schedule spec needs prompt and refs')
    if interval not in ('daily','weekly') or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',run_time):
        raise ValueError('Use daily|weekly and a UTC HH:MM time')
    now=now or datetime.now(timezone.utc)
    hour,minute=map(int,run_time.split(':'))
    next_run=now.replace(hour=hour,minute=minute,second=0,microsecond=0)
    if next_run<=now:next_run+=timedelta(days=1 if interval=='daily' else 7)
    id=uuid.uuid4().hex
    with db.conn:
        db.conn.execute('INSERT INTO schedules(id,spec_path,interval,next_run_at,run_time) VALUES(?,?,?,?,?)',
                        (id,str(spec_path),interval,next_run.isoformat(),run_time))
    return id

def _log(db,id,event,detail=''):
    with db.conn:
        db.conn.execute('INSERT INTO schedule_log(schedule_id,created_at,event,detail) VALUES(?,?,?,?)',
            (id,datetime.now(timezone.utc).isoformat(),event,detail))

def pipeline(db,root,schedule):
    spec_path=Path(schedule['spec_path']);spec=json.loads(spec_path.read_text())
    root=Path(root).resolve()
    base=[sys.executable,'-u','-m','foundry.cli','--root',str(root)]
    def call(args):
        result=subprocess.run(base+args,capture_output=True,text=True,env=dict(os.environ,PYTHONUNBUFFERED='1'))
        output=(result.stdout+result.stderr)[-20000:]
        for secret_name in ('YOUTUBE_API_KEY','OPENAI_API_KEY','OPENVERSE_API_KEY'):
            secret=os.environ.get(secret_name)
            if secret:output=output.replace(secret,'[redacted]')
        _log(db,schedule['id'],args[0],output)
        return result,output
    batch=schedule['batch_id'] if schedule['status']!='completed' else None
    if not batch:
        refs=Path(spec['refs'])
        if not refs.is_absolute():refs=spec_path.parent/refs
        args=['plan','--prompt',spec['prompt'],'--refs',str(refs),'--target',str(spec.get('target',200)),
              '--threshold',str(spec.get('threshold',.28))]
        # Scheduling is live unless the spec explicitly asks for offline fixtures.
        if not spec.get('offline',False):args.append('--live')
        result,output=call(args)
        if result.returncode:raise RuntimeError(output)
        batch=re.search(r'batch_id=([a-f0-9]+)',result.stdout)[1]
        with db.conn:
            db.conn.execute("UPDATE schedules SET batch_id=?,status='running' WHERE id=?",(batch,schedule['id']))
    from .quota import QuotaExceeded
    approved=db.conn.execute('SELECT qa_passed FROM batches WHERE id=?',(batch,)).fetchone()
    if not approved or not approved[0]:
        if schedule['status']!='awaiting_qa':
            for action in ('harvest','filter','qa'):
                args=[action,'--batch',batch]
                if action=='harvest' and spec.get('video_dir'):
                    path=Path(spec['video_dir'])
                    args+=['--video-dir',str(path if path.is_absolute() else spec_path.parent/path)]
                if action=='filter' and not spec.get('offline',False):args+=['--verifier','openai']
                result,output=call(args)
                if result.returncode==2:raise QuotaExceeded(output)
                if result.returncode:raise RuntimeError(output)
        approved=db.conn.execute('SELECT qa_passed FROM batches WHERE id=?',(batch,)).fetchone()
        if not approved[0]:
            verdicts=spec.get('verdicts')
            if not verdicts:return batch,'awaiting_qa'
            path=Path(str(verdicts).replace('{batch_id}',batch))
            if not path.is_absolute():path=spec_path.parent/path
            if not path.is_file():return batch,'awaiting_qa'
            result,output=call(['qa','--batch',batch,'--verdicts',str(path)])
            if result.returncode:raise RuntimeError(output)
    result,output=call(['package','--batch',batch])
    if result.returncode:raise RuntimeError(output)
    return batch,'completed'

def run_due(db,root,now=None,runner=None):
    now=now or datetime.now(timezone.utc);root=Path(root);root.mkdir(parents=True,exist_ok=True)
    shared=root/'web'/'pipeline.lock';shared.parent.mkdir(parents=True,exist_ok=True)
    due=db.conn.execute('SELECT * FROM schedules WHERE enabled=1 AND next_run_at<=? ORDER BY next_run_at',(now.isoformat(),)).fetchall()
    results=[]
    for record in due:
        schedule=dict(record);id=schedule['id']
        with (root/('schedule-'+id+'.lock')).open('w') as lock, shared.open('a') as pipeline_lock:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                _log(db,id,'skipped','Schedule already running')
                results.append({'id':id,'status':'skipped'});continue
            try:fcntl.flock(pipeline_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                _log(db,id,'skipped','Another schedule or web pipeline is running')
                results.append({'id':id,'status':'skipped'});continue
            current=db.conn.execute('SELECT * FROM schedules WHERE id=?',(id,)).fetchone()
            if not current or not current['enabled'] or datetime.fromisoformat(current['next_run_at'])>now:
                _log(db,id,'skipped','Schedule is no longer due after acquiring lock')
                results.append({'id':id,'status':'skipped'});continue
            schedule=dict(current)
            with db.conn:db.conn.execute('UPDATE schedules SET last_run_at=? WHERE id=?',(now.isoformat(),id))
            try:
                batch,status=(runner(schedule) if runner else pipeline(db,root,schedule))
                next_run=datetime.fromisoformat(schedule['next_run_at'])
                if status=='completed':
                    while next_run<=now:next_run+=timedelta(days=1 if schedule['interval']=='daily' else 7)
                with db.conn:
                    db.conn.execute('UPDATE schedules SET batch_id=?,status=?,next_run_at=?,last_error=? WHERE id=?',
                        (batch,status,next_run.isoformat(),'',id))
                _log(db,id,status,batch)
                results.append({'id':id,'batch_id':batch,'status':status})
            except Exception as error:
                with db.conn:db.conn.execute("UPDATE schedules SET status='failed',last_error=? WHERE id=?",(str(error),id))
                _log(db,id,'failed',str(error))
                from .quota import QuotaExceeded
                if isinstance(error,QuotaExceeded):raise
                results.append({'id':id,'status':'failed','error':str(error)})
    return results

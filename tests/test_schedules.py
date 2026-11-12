import json
from datetime import datetime,timezone
from foundry.db import Database
from foundry.scheduling import add_schedule, run_due

def test_creation_and_due_lock_and_qa_pause(tmp_path):
    db=Database(tmp_path/'db');spec=tmp_path/'spec.json'
    spec.write_text(json.dumps({'prompt':'glasses','refs':str(tmp_path/'refs')}))
    now=datetime(2026,1,1,9,0,tzinfo=timezone.utc)
    id=add_schedule(db,spec,'daily','10:00',now=now)
    assert db.conn.execute('select next_run_at from schedules').fetchone()[0].startswith('2026-01-01T10:00')
    events=[]
    def pipeline(schedule):
        events.append(schedule['id'])
        return 'batch','awaiting_qa'
    assert run_due(db,tmp_path,now=now,runner=pipeline)==[]
    results=run_due(db,tmp_path,now=datetime(2026,1,1,11,0,tzinfo=timezone.utc),runner=pipeline)
    assert results[0]['status']=='awaiting_qa' and events==[id]
    assert db.conn.execute('select batch_id from schedules').fetchone()[0]=='batch'
    import fcntl
    with (tmp_path/('schedule-'+id+'.lock')).open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        results=run_due(db,tmp_path,now=datetime(2026,1,1,11,1,tzinfo=timezone.utc),runner=pipeline)
        assert results[0]['status']=='skipped'
    def complete(schedule):
        assert schedule['batch_id']=='batch'
        return 'batch','completed'
    run_due(db,tmp_path,now=datetime(2026,1,1,11,2,tzinfo=timezone.utc),runner=complete)
    assert db.conn.execute('select next_run_at from schedules').fetchone()[0].startswith('2026-01-02T10:00')

def test_weekly_and_validation(tmp_path):
    import pytest
    db=Database(tmp_path/'db');spec=tmp_path/'s.json';spec.write_text('{}')
    with pytest.raises(ValueError):add_schedule(db,spec,'hourly','99:00')

def test_real_scheduled_pipeline_waits_for_qa_then_resumes(tmp_path):
    from click.testing import CliRunner
    from PIL import Image
    from foundry.cli import cli
    import csv
    refs=tmp_path/'refs';refs.mkdir()
    for i in range(6):Image.new('RGB',(16,16),(i*30,0,0)).save(refs/f'{i}.png')
    root=tmp_path/'data';spec=tmp_path/'spec.json'
    spec.write_text(json.dumps({'prompt':'scheduled fixture','refs':'refs','offline':True}))
    runner=CliRunner();base=['--root',str(root)]
    result=runner.invoke(cli,base+['schedule','add','--spec',str(spec),'--interval','daily','--time','10:00'])
    assert result.exit_code==0,result.output
    id=result.output.strip()
    db=Database(root/'foundry.sqlite3')
    with db.conn:db.conn.execute("update schedules set next_run_at='2020-01-01T10:00:00+00:00' where id=?",(id,))
    result=runner.invoke(cli,base+['run-scheduled'])
    assert result.exit_code==0,result.output
    record=db.conn.execute('select * from schedules').fetchone()
    assert record['status']=='awaiting_qa'
    batch=record['batch_id']
    assert not list((root/'packages').glob('*/manifest.csv'))
    before=db.conn.execute('select count(*) from drops').fetchone()[0]
    result=runner.invoke(cli,base+['run-scheduled'])
    assert result.exit_code==0,result.output
    assert db.conn.execute('select count(*) from drops').fetchone()[0]==before
    records=list(db.conn.execute('select row_id from qa_samples where batch_id=?',(batch,)))
    path=tmp_path/'review.csv'
    with path.open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['id','verdict'])
        writer.writerows((r[0],'accept') for r in records)
    result=runner.invoke(cli,base+['qa','--batch',batch,'--verdicts',str(path)])
    assert result.exit_code==0,result.output
    result=runner.invoke(cli,base+['run-scheduled'])
    assert result.exit_code==0,result.output
    assert db.conn.execute('select status from schedules').fetchone()[0]=='completed'
    assert len(list((root/'packages').glob('*/manifest.csv')))==1

def test_due_rows_are_rechecked_after_lock(tmp_path):
    db=Database(tmp_path/'db');spec=tmp_path/'spec.json'
    spec.write_text(json.dumps({'prompt':'x','refs':'refs'}))
    now=datetime(2026,1,1,9,tzinfo=timezone.utc)
    first=add_schedule(db,spec,'daily','10:00',now=now)
    second=add_schedule(db,spec,'daily','10:01',now=now)
    def runner(schedule):
        assert schedule['id']==first
        with db.conn:db.conn.execute("update schedules set next_run_at='2026-01-02T10:01:00+00:00' where id=?",(second,))
        return 'batch','completed'
    result=run_due(db,tmp_path,now=datetime(2026,1,1,11,tzinfo=timezone.utc),runner=runner)
    assert result[-1]['status']=='skipped'

def test_schedule_respects_web_pipeline_lock(tmp_path):
    import fcntl
    db=Database(tmp_path/'db');spec=tmp_path/'s.json'
    spec.write_text(json.dumps({'prompt':'x','refs':'refs'}))
    now=datetime(2026,1,1,9,tzinfo=timezone.utc)
    add_schedule(db,spec,'daily','10:00',now=now)
    directory=tmp_path/'web';directory.mkdir()
    with (directory/'pipeline.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        def not_called(_):raise AssertionError('Pipeline must not run')
        result=run_due(db,tmp_path,now=datetime(2026,1,1,11,tzinfo=timezone.utc),runner=not_called)
        assert result[0]['status']=='skipped'

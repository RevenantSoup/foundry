import csv
import json
from pathlib import Path
import pytest
from click.testing import CliRunner
from PIL import Image
from foundry.cli import cli
from foundry.db import Database

def refs(path):
    path.mkdir()
    for i in range(6): Image.new('RGB',(20,20),(i*30,0,0)).save(path/f'{i}.png')

def invoke(runner,root,*args):
    return runner.invoke(cli,['--root',str(root),*args])

def test_offline_full_pipeline_and_resume(tmp_path):
    refs(tmp_path/'refs'); runner=CliRunner(); root=tmp_path/'data'
    result=invoke(runner,root,'plan','--prompt','people in safety glasses','--refs',str(tmp_path/'refs'))
    assert result.exit_code==0,result.output
    plans=list((root/'plans').glob('*.json')); assert len(plans)==1
    plan=json.loads(plans[0].read_text()); batch=plan['batch_id']
    assert set(('search_terms','hashtags','negative_terms','checklist','threshold'))<=plan.keys()
    for command in ('harvest','harvest','filter','filter','qa'):
        result=invoke(runner,root,command,'--batch',batch)
        assert result.exit_code==0,(command,result.output,result.exception)
    assert invoke(runner,root,'package','--batch',batch).exit_code==1
    verdicts=root/'qa'/batch/'verdicts.csv'
    records=list(csv.DictReader(verdicts.open()))
    with verdicts.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['id','verdict']); w.writeheader()
        for i,row in enumerate(records): row['verdict']='reject' if i<21 else 'accept'; w.writerow(row)
    result=invoke(runner,root,'qa','--batch',batch,'--verdicts',str(verdicts))
    assert result.exit_code==1 and 'failing IDs' in result.output
    assert invoke(runner,root,'package','--batch',batch).exit_code==1
    assert invoke(runner,root,'qa','--batch',batch,'--stub-verdicts','accept').exit_code==0
    result=invoke(runner,root,'package','--batch',batch)
    assert result.exit_code==0,result.output
    manifests=list((root/'packages').glob('*/manifest.csv')); assert len(manifests)==1
    records=list(csv.DictReader(manifests[0].open())); assert len(records)==200
    assert all(all(v for v in r.values()) for r in records)
    db=Database(root/'foundry.sqlite3')
    assert {r.source for r in db.rows(batch)}=={'openverse','youtube'}

def test_dead_source_isolated(tmp_path,monkeypatch):
    refs(tmp_path/'refs'); runner=CliRunner(); root=tmp_path/'data'
    result=invoke(runner,root,'plan','--prompt','x','--refs',str(tmp_path/'refs'))
    batch=json.loads(next((root/'plans').glob('*.json')).read_text())['batch_id']
    def dead(*args): raise OSError('dead source')
    monkeypatch.setattr('foundry.cli.OpenverseAdapter.search',dead)
    result=invoke(runner,root,'harvest','--batch',batch)
    assert result.exit_code==0 and 'dead source' in result.output
    assert {r.source for r in Database(root/'foundry.sqlite3').rows(batch)}=={'youtube'}

def test_cli_quota_exit_two(tmp_path,monkeypatch):
    refs(tmp_path/'refs'); runner=CliRunner(); root=tmp_path/'data'
    invoke(runner,root,'plan','--prompt','x','--refs',str(tmp_path/'refs'),'--live')
    batch=json.loads(next((root/'plans').glob('*.json')).read_text())['batch_id']
    from foundry.quota import consume
    db=Database(root/'foundry.sqlite3'); consume(db,'youtube',10000); db.close()
    monkeypatch.setenv('YOUTUBE_API_KEY','fake')
    monkeypatch.setattr('foundry.cli.OpenverseAdapter.search',lambda *a:[])
    result=invoke(runner,root,'harvest','--batch',batch)
    assert result.exit_code==2,result.output

@pytest.mark.parametrize('command',['plan','harvest','filter','qa','package'])
def test_help(command):
    assert CliRunner().invoke(cli,[command,'--help']).exit_code==0

def test_ffmpeg_source_failure_isolated(tmp_path,monkeypatch):
    import ffmpeg
    refs(tmp_path/'refs'); runner=CliRunner(); root=tmp_path/'data'
    invoke(runner,root,'plan','--prompt','x','--refs',str(tmp_path/'refs'))
    batch=json.loads(next((root/'plans').glob('*.json')).read_text())['batch_id']
    def broken(*args): raise ffmpeg.Error('ffmpeg',b'',b'invalid video')
    monkeypatch.setattr('foundry.cli.YouTubeAdapter.search',broken)
    result=invoke(runner,root,'harvest','--batch',batch,'--limit','2')
    assert result.exit_code==0,result.exception
    assert {r.source for r in Database(root/'foundry.sqlite3').rows(batch)}=={'openverse'}

def test_existing_id_with_changed_url_preserves_bytes(tmp_path,monkeypatch):
    refs(tmp_path/'refs'); runner=CliRunner(); root=tmp_path/'data'
    invoke(runner,root,'plan','--prompt','x','--refs',str(tmp_path/'refs'))
    batch=json.loads(next((root/'plans').glob('*.json')).read_text())['batch_id']
    assert invoke(runner,root,'harvest','--batch',batch,'--limit','1').exit_code==0
    row=next(r for r in Database(root/'foundry.sqlite3').rows(batch) if r.source=='openverse')
    path=root/'raw'/row.id; original=path.read_bytes()
    row.source_url+='/changed'
    monkeypatch.setattr('foundry.cli.OpenverseAdapter.search',lambda *args:[row])
    result=invoke(runner,root,'harvest','--batch',batch,'--limit','1')
    assert result.exit_code==0,result.output
    assert path.exists() and path.read_bytes()==original

import pytest
import requests
from foundry.db import Database
from foundry.http import request_with_retry
from foundry.quota import consume, QuotaExceeded

class Response:
    def __init__(self,status,data=None): self.status_code=status; self.data=data or {};self.headers={}
    def json(self):return self.data
    def raise_for_status(self):
        if self.status_code>=400:raise requests.HTTPError('HTTP '+str(self.status_code))

class Session:
    def __init__(self,responses):self.responses=iter(responses);self.calls=0
    def get(self,*args,**kwargs):self.calls+=1;return next(self.responses)

def test_backoff_and_usage(tmp_path):
    db=Database(tmp_path/'db'); waits=[];session=Session([Response(429),Response(503),Response(200)])
    result=request_with_retry(session,'get','https://example.org',db=db,source='openverse',sleep=waits.append)
    assert result.status_code==200 and waits==[1,2] and session.calls==3
    records=db.conn.execute('select * from usage_log').fetchall()
    assert len(records)==3 and records[0]['status_code']==429 and records[-1]['retry_count']==2

def test_max_three_retries_then_fail(tmp_path):
    session=Session([Response(500)]*4)
    with pytest.raises(requests.HTTPError):request_with_retry(session,'get','https://example.org',sleep=lambda _:None)
    assert session.calls==4

def test_quota_every_retry_and_provider_exhaustion(tmp_path):
    db=Database(tmp_path/'db');session=Session([Response(500),Response(403,{'error':{'errors':[{'reason':'quotaExceeded'}]}})])
    with pytest.raises(QuotaExceeded):request_with_retry(session,'get','https://example.org',db=db,source='youtube',sleep=lambda _:None,charge=lambda:consume(db,'youtube',100))
    assert db.conn.execute('select units from quota').fetchone()[0]==200
    with pytest.raises(QuotaExceeded,match='remaining'):consume(db,'youtube',100)

def test_openverse_metadata_and_rejection_log(tmp_path):
    from foundry.adapters.openverse import OpenverseAdapter
    db=Database(tmp_path/'db')
    valid={'id':'good','url':'https://example.org/a.jpg','foreign_landing_url':'https://example.org/a','creator':'Alice','title':'Safety','license':'by','license_url':'https://creativecommons.org/licenses/by/4.0/'}
    session=Session([Response(200,{'results':[dict(valid,id='bad',creator=''),valid],'next':'next'}),Response(200,{'results':[dict(valid,id='second')],'next':None})])
    adapter=OpenverseAdapter(offline=False,session=session,db=db,batch_id='batch')
    rows=adapter.search('safety',2)
    assert len(rows)==2 and rows[0].metadata['title']=='Safety'
    assert db.conn.execute('select reason from drops').fetchone()[0]=='missing_licence_or_attribution'

def test_openai_retry_tokens_and_fail_closed(tmp_path,monkeypatch):
    from PIL import Image
    from foundry.cascade.verify import OpenAIVerifier
    monkeypatch.setattr('foundry.http.time.sleep',lambda _:None)
    db=Database(tmp_path/'db');image=tmp_path/'image.png';Image.new('RGB',(16,16),'red').save(image)
    class Post(Session):
        def post(self,*args,**kwargs):return self.get(*args,**kwargs)
    session=Post([Response(429),Response(200,{'choices':[{'message':{'content':'accept'}}],'usage':{'total_tokens':19}})])
    verifier=OpenAIVerifier('key',session=session,db=db,batch_id='b')
    assert verifier.verify(image,'red',['red'])=='accept'
    assert db.conn.execute("select sum(token_count) from usage_log where source='openai'").fetchone()[0]==19
    verifier.session=Post([Response(200,{'choices':[{'message':{'content':'maybe'}}]})])
    with pytest.raises(ValueError):verifier.verify(image,'red',['red'])
    assert db.conn.execute("select count(*) from usage_log where event='validation'").fetchone()[0]==1

def test_provider_errors_never_echo_credentials():
    class Leaky(Response):
        def raise_for_status(self):
            raise requests.HTTPError('Forbidden https://provider.example?key=secret-token')
    with pytest.raises(requests.HTTPError) as error:
        request_with_retry(Session([Leaky(403)]),'get','https://provider.example',source='youtube')
    assert 'secret-token' not in str(error.value) and '403' in str(error.value)

def test_exhausted_live_fetch_fails_after_saving_other_source(tmp_path,monkeypatch):
    from click.testing import CliRunner
    from foundry.cli import cli
    from tests.test_cli import refs
    from foundry.adapters.base import fixture_rows,fixture_bytes
    refs(tmp_path/'refs');root=tmp_path/'data';runner=CliRunner();base=['--root',str(root)]
    result=runner.invoke(cli,base+['plan','--prompt','x','--refs',str(tmp_path/'refs'),'--live'])
    import json
    batch=json.loads(next((root/'plans').glob('*.json')).read_text())['batch_id']
    monkeypatch.setattr('foundry.cli.OpenverseAdapter.search',lambda *args:fixture_rows('openverse','x',1,'CC0'))
    monkeypatch.setattr('foundry.cli.YouTubeAdapter.search',lambda *args:fixture_rows('youtube','x',1,'platform_public_as_is'))
    def failed(*args):raise requests.HTTPError('openverse HTTP 429; retries exhausted')
    monkeypatch.setattr('foundry.cli.OpenverseAdapter.fetch',failed)
    monkeypatch.setattr('foundry.cli.YouTubeAdapter.fetch',lambda self,row:fixture_bytes(row))
    result=runner.invoke(cli,base+['harvest','--batch',batch])
    assert result.exit_code==1,result.output
    assert {r.source for r in Database(root/'foundry.sqlite3').rows(batch)}=={'youtube'}

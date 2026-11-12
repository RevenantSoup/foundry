from tests.test_marketplace import listed
from foundry.buyers import create_key,revoke_key
from web.bridge import buyer_request

def test_auth_status_manifest_and_placeholder(listed,monkeypatch):
    db,path=listed
    monkeypatch.setenv('FOUNDRY_ROOT',str(path.parent.parent))
    assert buyer_request({})['status']==401
    id,key=create_key(db,'buyer')
    result=buyer_request({'token':key,'id':path.name,'manifest':True})
    assert result['status']==200
    assert result['body']['attribution']
    assert len(result['body']['provenance_hash'])==64
    assert all(r['attribution'] and r['licence'] for r in result['body']['images'])
    assert buyer_request({'token':key,'checkout':True})['status']==501
    assert buyer_request({'token':key,'params':{'source':'openverse','licence':'CC0','min_size':'200','free':'true'}})['body']['total']==1
    revoke_key(db,id)
    assert buyer_request({'token':key})['status']==403

def test_usage_reports_daily_quota_remaining(tmp_path,monkeypatch):
    from foundry.db import Database
    from foundry.quota import consume
    from web.bridge import usage_payload
    monkeypatch.setenv('FOUNDRY_ROOT',str(tmp_path))
    db=Database(tmp_path/'foundry.sqlite3')
    consume(db,'youtube',8000)
    result=usage_payload()
    assert result['youtube']['used']==8000 and result['youtube']['remaining']==2000
    row=next(r for r in result['daily'] if r['source']=='youtube')
    assert row['quota_used']==8000 and row['quota_remaining']==2000

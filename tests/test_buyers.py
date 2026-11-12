import hashlib
from foundry.db import Database
from foundry.buyers import create_key, revoke_key, authorize

def test_keys_hashed_revoked_and_rate_limited(tmp_path):
    db=Database(tmp_path/'db')
    assert authorize(db,None)['status']==401
    id,key=create_key(db,'acme')
    record=dict(db.conn.execute('select * from api_keys').fetchone())
    assert record['key_hash']==hashlib.sha256(key.encode()).hexdigest()
    assert key not in str(record)
    for _ in range(60):assert authorize(db,key,now=120)['status']==200
    limited=authorize(db,key,now=120)
    assert limited['status']==429 and limited['headers']['Retry-After']=='60'
    assert authorize(db,key,now=180)['status']==200
    revoke_key(db,id)
    assert authorize(db,key,now=180)['status']==403

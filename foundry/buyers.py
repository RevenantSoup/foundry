"""Buyer keys authorize dataset reads and test checkout, hashed at rest and rate limited in SQLite."""
from datetime import datetime, timezone
import hashlib
import secrets
import time
import uuid

def create_key(db,name):
    if not name.strip() or len(name)>200:raise ValueError('Key name must contain 1–200 characters')
    id=uuid.uuid4().hex
    key='fdy_'+secrets.token_urlsafe(32)
    with db.conn:
        db.conn.execute('INSERT INTO api_keys(id,key_hash,name,created_at) VALUES(?,?,?,?)',
            (id,hashlib.sha256(key.encode()).hexdigest(),name.strip(),datetime.now(timezone.utc).isoformat()))
    return id,key

def revoke_key(db,id):
    with db.conn:
        cursor=db.conn.execute('UPDATE api_keys SET is_active=0,revoked_at=? WHERE id=?',
            (datetime.now(timezone.utc).isoformat(),id))
        if not cursor.rowcount:raise ValueError('Unknown key ID')

def authorize(db,key,now=None):
    headers={'Cache-Control':'no-store'}
    if not key or len(key)>512:
        return {'status':401,'body':{'error':'unauthorized'},'headers':headers}
    stamp=int(time.time() if now is None else now);window=stamp//60*60
    with db.conn:
        db.conn.execute('BEGIN IMMEDIATE')
        row=db.conn.execute('SELECT * FROM api_keys WHERE key_hash=?',(hashlib.sha256(key.encode()).hexdigest(),)).fetchone()
        if not row:return {'status':401,'body':{'error':'invalid_api_key'},'headers':headers}
        if not row['is_active'] or row['revoked_at']:
            return {'status':403,'body':{'error':'revoked_api_key'},'headers':headers}
        db.conn.execute('INSERT OR IGNORE INTO api_rate_limits VALUES(?,?,0)',(row['id'],window))
        used=db.conn.execute('SELECT requests FROM api_rate_limits WHERE key_id=? AND window_start=?',(row['id'],window)).fetchone()[0]
        now_iso=datetime.fromtimestamp(stamp,timezone.utc).isoformat()
        status=429 if used>=60 else 200
        if status==200:
            db.conn.execute('UPDATE api_rate_limits SET requests=requests+1 WHERE key_id=? AND window_start=?',(row['id'],window))
            db.conn.execute('UPDATE api_keys SET last_used_at=? WHERE id=?',(now_iso,row['id']))
        db.conn.execute('INSERT INTO usage_log(source,batch_id,day,created_at,event,status_code,is_error,detail) VALUES(?,?,?,?,?,?,?,?)',
            ('buyer',row['id'],now_iso[:10],now_iso,'request',status,int(status>=400),'read_only_api'))
        db.conn.execute('DELETE FROM api_rate_limits WHERE window_start<?',(window-3600,))
        if status==429:
            return {'status':429,'body':{'error':'rate_limit_exceeded'},'headers':{**headers,'Retry-After':str(window+60-stamp)}}
        return {'status':200,'key_id':row['id'],'headers':headers}

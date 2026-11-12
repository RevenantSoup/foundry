"""TEST ONLY. Explicit fake rights metadata under the isolated browser-test root."""
import csv
import json
import os
from pathlib import Path
import random
import sys
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from PIL import Image
from foundry.db import Database
from foundry.models import Row
from foundry.buyers import create_key
from foundry.qa import create_sheet,read_verdicts
from foundry.package import package_batch
from foundry.marketplace import set_price

root=Path(os.environ['FOUNDRY_ROOT']).resolve()
if root.name!='web-test-data':raise RuntimeError('Fixture only supports isolated web-test-data')
root.mkdir(parents=True,exist_ok=True);raw=root/'raw';raw.mkdir(exist_ok=True)
db=Database(root/'foundry.sqlite3')
batch=uuid.uuid4().hex;prompt='TEST marketplace safety glasses '+batch[:6]
with db.conn:db.conn.execute('INSERT INTO batches(id,plan) VALUES(?,?)',(batch,json.dumps({'prompt':prompt,'attribute':'safety glasses','target':200,'offline':False})))
rng=random.Random(batch)
for i in range(200):
    id=batch+f'{i:03d}'
    row=Row(id,'openverse','https://example.org/TEST-ONLY/'+id,'CC-BY','Test creator — fixture only',
            phash=f'{rng.getrandbits(64):016x}',clip_score=.8,vlm_verdict='accept',batch_id=batch)
    assert db.insert(row)
    Image.new('RGB',(64,64),(i,80,120)).save(raw/id,format='PNG')
sheet,template=create_sheet(db,batch,raw,root/'qa'/batch)
with template.open('w',newline='') as stream:
    writer=csv.writer(stream);writer.writerow(['id','verdict'])
    writer.writerows((r[0],'accept') for r in db.conn.execute('SELECT row_id FROM qa_samples WHERE batch_id=?',(batch,)))
read_verdicts(db,batch,template)
package=package_batch(db,batch,raw,root/'packages')
id,key=create_key(db,'browser-test-only')
revoked_id,revoked=create_key(db,'revoked-browser-test')
from foundry.buyers import revoke_key
revoke_key(db,revoked_id)
rate_id,rate=create_key(db,'rate-browser-test')
# Plaintext test keys are returned once to the in-memory test runner, never written to files.
print(json.dumps({'dataset':package.name,'batch':batch,'prompt':prompt,'key':key,'key_id':id,'revoked':revoked,'rate':rate}))

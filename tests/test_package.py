import csv
import json
import pytest
from PIL import Image
from foundry.db import Database
from foundry.models import Row
from foundry.qa import create_sheet, read_verdicts, selected_rows, check_qa
from foundry.package import package_batch

def dataset(tmp_path):
    db=Database(tmp_path/'db')
    plan={'target':200}
    db.conn.execute('insert into batches(id,plan) values(?,?)',('b',json.dumps(plan)))
    raw=tmp_path/'raw'; raw.mkdir()
    import random
    rng=random.Random(123)
    for i in range(200):
        r=Row(str(i),'test','https://example.org/'+str(i),'CC0','Author',
              phash=f'{rng.getrandbits(64):016x}',clip_score=.8,vlm_verdict='accept',batch_id='b')
        assert db.insert(r)
        Image.new('RGB',(20,20),(i,0,0)).save(raw/r.id,format='PNG')
    return db,raw

def verdict_file(db,path,bad=0):
    with path.open('w',newline='') as f:
        writer=csv.writer(f); writer.writerow(['id','verdict'])
        for i,row in enumerate(db.conn.execute('select row_id from qa_samples order by position')):
            writer.writerow([row[0],'reject' if i<bad else 'accept'])

def test_qa_blocks_and_package_versions(tmp_path):
    db,raw=dataset(tmp_path)
    with pytest.raises(ValueError): package_batch(db,'b',raw,tmp_path/'packages')
    sheet,template=create_sheet(db,'b',raw,tmp_path/'qa')
    assert Image.open(sheet).size == (1600,2880)
    assert len(list(csv.DictReader(template.open())))==200
    verdict_file(db,template,21)
    with pytest.raises(ValueError,match='Precision'):
        read_verdicts(db,'b',template)
    with pytest.raises(ValueError):
        package_batch(db,'b',raw,tmp_path/'packages')
    verdict_file(db,template,20)
    assert read_verdicts(db,'b',template)==.90
    path=package_batch(db,'b',raw,tmp_path/'packages')
    rows=list(csv.DictReader((path/'manifest.csv').open()))
    assert len(rows)==200 and sum(r['split']=='train' for r in rows)==180
    assert all(all(v != '' for v in row.values()) for row in rows)
    assert package_batch(db,'b',raw,tmp_path/'packages')==path
    (raw/'0').write_bytes(b'tampered')
    with pytest.raises(ValueError,match='changed'):
        package_batch(db,'b',raw,tmp_path/'packages')

def test_package_null_licence_refused(tmp_path):
    db,raw=dataset(tmp_path)
    create_sheet(db,'b',raw,tmp_path/'qa')
    template=tmp_path/'verdict.csv'; verdict_file(db,template)
    read_verdicts(db,'b',template)
    db.conn.execute('PRAGMA ignore_check_constraints=ON')
    db.conn.execute("update rows set licence='' where id='0'")
    db.conn.commit()
    with pytest.raises(ValueError,match='licence'):
        package_batch(db,'b',raw,tmp_path/'packages')

def test_incomplete_verdicts_do_not_pass(tmp_path):
    db,raw=dataset(tmp_path)
    _,template=create_sheet(db,'b',raw,tmp_path/'qa')
    with pytest.raises(ValueError):
        read_verdicts(db,'b',template)

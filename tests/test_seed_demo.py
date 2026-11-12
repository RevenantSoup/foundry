import csv
from foundry.seed import seed_demo
from foundry.db import Database

def test_demo_idempotent_and_not_saleable(tmp_path):
    first=seed_demo(tmp_path);second=seed_demo(tmp_path)
    assert first==second and len(first)==2
    db=Database(tmp_path/'foundry.sqlite3')
    assert db.conn.execute('select count(*) from batches').fetchone()[0]==2
    assert db.conn.execute('select sum(saleable) from datasets').fetchone()[0]==0
    assert all(db.conn.execute('select count(*) from qa_samples where batch_id=?',(item['batch_id'],)).fetchone()[0]==200 for item in first)
    for item in first:
        with (tmp_path/'packages'/item['dataset_id']/'manifest.csv').open() as stream:
            rows=list(csv.DictReader(stream))
        assert len(rows)==200 and all(row['licence'] and row['attribution'] for row in rows)

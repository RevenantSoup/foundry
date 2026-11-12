import sqlite3
import pytest
from foundry.db import Database
from foundry.models import Row, write_manifest

def row(id='a', **kw):
    return Row(id=id, source='test', source_url='https://example.org/'+id,
               licence='CC0', attribution='Author', phash='0000000000000000', **kw)

def test_rights_required(tmp_path):
    db = Database(tmp_path/'db')
    r = row(); r.licence = ''
    with pytest.raises((ValueError, sqlite3.IntegrityError)): db.insert(r)
    r.licence = 'CC0'; r.attribution = ' '
    with pytest.raises((ValueError, sqlite3.IntegrityError)): db.insert(r)

def test_global_dedupe_and_log(tmp_path):
    db = Database(tmp_path/'db')
    assert db.insert(row(batch_id='one'))
    assert not db.insert(row('b', batch_id='two'))
    assert db.conn.execute('select reason from drops').fetchone()[0] == 'phash'
    assert db.conn.execute('select count(*) from seen_urls').fetchone()[0] == 2

def test_manifest_refuses_null_rights(tmp_path):
    r = row(); r.licence = None
    with pytest.raises(ValueError): write_manifest(tmp_path/'manifest.csv', [r])

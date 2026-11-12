import importlib.util
from pathlib import Path
import pytest

SPEC=importlib.util.spec_from_file_location('bridge',Path(__file__).parents[1]/'bridge.py')
bridge=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)

def test_empty_snapshot(tmp_path,monkeypatch):
    monkeypatch.setenv('FOUNDRY_ROOT',str(tmp_path))
    state=bridge.snapshot()
    assert state['batches']==[] and state['totals']['harvested']==0

def test_path_validation():
    with pytest.raises(ValueError): bridge.identifier('../escape')
    with pytest.raises(ValueError): bridge.identifier('bad/name')

def test_unknown_action_rejected(tmp_path,monkeypatch):
    monkeypatch.setenv('FOUNDRY_ROOT',str(tmp_path))
    with pytest.raises(ValueError): bridge.command_for('delete','a'*32,{})

def test_platform_rights_not_for_sale():
    assert bridge.sale_clearance(['CC0','CC-BY'])
    assert not bridge.sale_clearance(['CC0','platform_public_as_is'])
    assert not bridge.sale_clearance(['unknown'])

def test_newest_package_not_lexical_hash(tmp_path,monkeypatch):
    import csv,json,os
    from foundry.db import Database
    monkeypatch.setenv('FOUNDRY_ROOT',str(tmp_path))
    db=Database(tmp_path/'foundry.sqlite3')
    with db.conn: db.conn.execute("insert into batches(id,plan) values(?,?)",('b',json.dumps({'prompt':'x','offline':True})))
    db.close()
    for name,count,created in [('b-zzz',2,100),('b-aaa',3,200)]:
        directory=tmp_path/'packages'/name;directory.mkdir(parents=True)
        manifest=directory/'manifest.csv'
        with manifest.open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=['licence','attribution','source_url','split','provenance_hash'])
            writer.writeheader()
            for i in range(count):writer.writerow({'licence':'CC0','attribution':'Author','source_url':'stub://x','split':'train','provenance_hash':str(i)})
        (directory/'dataset.json').write_text(json.dumps({'batch_id':'b','version':name,'count':count}))
        os.utime(manifest,(created,created))
    assert bridge.snapshot()['batches'][0]['packaged']==3

def test_secrets_redacted_from_logs(monkeypatch):
    monkeypatch.setenv('YOUTUBE_API_KEY','private-key')
    assert bridge.redact('HTTP error ?key=private-key')=='HTTP error ?key=[redacted]'

def test_listing_prices_persist_and_restricted_prices_fail(tmp_path,monkeypatch):
    import csv,json
    monkeypatch.setenv('FOUNDRY_ROOT',str(tmp_path))
    directory=tmp_path/'packages'/'cleared';directory.mkdir(parents=True)
    (directory/'dataset.json').write_text(json.dumps({'batch_id':'b','version':'v','count':1}))
    with (directory/'manifest.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['licence','attribution','source_url','split','provenance_hash'])
        writer.writeheader();writer.writerow({'licence':'CC-BY','attribution':'Author','source_url':'https://example.org/image','split':'train','provenance_hash':'hash'})
    assert bridge.price({'package':'cleared','price':42.25})=={'price':42.25}
    assert bridge.read_packages()[0]['price']==42.25
    with pytest.raises(ValueError):bridge.price({'package':'cleared','price':-1})
    manifest=directory/'manifest.csv'
    manifest.write_text(manifest.read_text().replace('CC-BY','platform_public_as_is'))
    with pytest.raises(ValueError,match='rights-cleared'):bridge.price({'package':'cleared','price':3})

def test_negative_cosine_scores_have_an_honest_distribution(tmp_path,monkeypatch):
    from foundry.db import Database
    from foundry.models import Row
    monkeypatch.setenv('FOUNDRY_ROOT',str(tmp_path))
    db=Database(tmp_path/'foundry.sqlite3')
    db.insert(Row('negative','test','https://example.org/x','CC0','Author',phash='0000000000000000',clip_score=-.3))
    db.close()
    bands=bridge.snapshot()['distribution']
    assert sum(band['value'] for band in bands)==1
    assert next(band for band in bands if band['value']==1)['name'].startswith('-')

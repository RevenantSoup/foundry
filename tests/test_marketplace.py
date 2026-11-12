import hashlib
import pytest
from foundry.db import Database
from foundry.marketplace import register_dataset, search_datasets, dataset_detail, set_price, buyer_manifest
from tests.test_package import dataset, verdict_file
from foundry.qa import create_sheet, read_verdicts
from foundry.package import package_batch

@pytest.fixture
def listed(tmp_path):
    db,raw=dataset(tmp_path)
    db.close();(tmp_path/'db').rename(tmp_path/'foundry.sqlite3')
    db=Database(tmp_path/'foundry.sqlite3')
    with db.conn:
        db.conn.execute("update rows set source='openverse'")
    create_sheet(db,'b',raw,tmp_path/'qa')
    verdicts=tmp_path/'verdict.csv';verdict_file(db,verdicts)
    read_verdicts(db,'b',verdicts)
    output=package_batch(db,'b',raw,tmp_path/'packages')
    return db,output

def test_registry_defaults_hash_and_attribution(listed):
    db,path=listed
    detail=dataset_detail(db,path.name)
    assert detail['price_cents']==0 and detail['currency']=='USD'
    assert detail['manifest_sha256']==hashlib.sha256((path/'manifest.csv').read_bytes()).hexdigest()
    assert detail['saleable'] and len(detail['samples'])==12
    manifest=buyer_manifest(db,path.name)
    assert manifest['attribution'] and len(manifest['images'])==200 and manifest['provenance_hash']==detail['manifest_sha256']

def test_combined_filters_and_price(listed):
    db,path=listed
    set_price(db,path.name,4999)
    assert search_datasets(db,{'q':'b','licence':'CC0','source':'openverse','min_size':'200','max_size':'300','min_price':'40','max_price':'50'})['total']==1
    assert search_datasets(db,{'free':'true'})['total']==0
    assert search_datasets(db,{'source':'youtube'})['total']==0
    with pytest.raises(ValueError):set_price(db,path.name,-1)

def test_tamper_and_missing_rights_unavailable(listed):
    db,path=listed
    file=path/'manifest.csv';file.write_text(file.read_text().replace('CC0','UNKNOWN'))
    register_dataset(db,path)
    assert not dataset_detail(db,path.name)['saleable']
    assert search_datasets(db,{})['total']==0

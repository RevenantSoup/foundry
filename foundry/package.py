"""Content-versioned, reproducible dataset packaging with QA enforcement."""
import hashlib
import json
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path
from .models import validate_rights, write_manifest
from .qa import selected_rows, check_qa

def package_batch(db,batch,raw,destination):
    # Validate all batch records, including records not selected for export.
    for row in db.rows(batch):
        validate_rights(row)
    check_qa(db,batch,raw)
    rows=selected_rows(db,batch)
    if not rows:
        raise ValueError('No accepted rows')
    for index,row in enumerate(sorted(rows,key=lambda r:hashlib.sha256(r.id.encode()).hexdigest())):
        row.split='train' if index < int(len(rows)*.9) else 'validation'
        row.qa_verdict=row.qa_verdict or 'not_sampled'
        payload=(Path(raw)/row.id).read_bytes()
        provenance={k:v for k,v in asdict(row).items() if k!='provenance_hash'}
        provenance['sha256']=hashlib.sha256(payload).hexdigest()
        row.provenance_hash=hashlib.sha256(json.dumps(provenance,sort_keys=True).encode()).hexdigest()
    version=hashlib.sha256(''.join(r.provenance_hash for r in rows).encode()).hexdigest()[:16]
    destination=Path(destination); destination.mkdir(parents=True,exist_ok=True)
    output=destination/f'{batch}-{version}'
    if not output.exists():
        staging=Path(tempfile.mkdtemp(prefix='.package-',dir=destination))
        try:
            images=staging/'images'; images.mkdir()
            for row in rows:
                shutil.copyfile(Path(raw)/row.id,images/row.id)
            write_manifest(staging/'manifest.csv',rows)
            (staging/'dataset.json').write_text(json.dumps({'batch_id':batch,'version':version,'count':len(rows),
                'manifest_sha256':hashlib.sha256((staging/'manifest.csv').read_bytes()).hexdigest()},indent=2))
            staging.rename(output)
        finally:
            if staging.exists(): shutil.rmtree(staging)
    for row in rows:
        db.update(row.id,split=row.split,qa_verdict=row.qa_verdict,provenance_hash=row.provenance_hash)
    from .marketplace import register_dataset
    register_dataset(db,output)
    return output

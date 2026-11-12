"""SQLite dataset registry, manifest fingerprints, and parameterized discovery."""
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

LICENCES={'CC0','CC-BY','CC-BY-SA','platform_public_as_is'}
SOURCES={'openverse','youtube'}
LICENCE_URLS={
 'CC0':'https://creativecommons.org/publicdomain/zero/1.0/',
 'CC-BY':'https://creativecommons.org/licenses/by/',
 'CC-BY-SA':'https://creativecommons.org/licenses/by-sa/',
 'platform_public_as_is':'https://www.youtube.com/static?template=terms',
}

def _rows(path):
    with Path(path).open(newline='',encoding='utf-8') as stream:
        return list(csv.DictReader(stream))

def register_dataset(db,directory):
    directory=Path(directory).resolve()
    manifest=directory/'manifest.csv'
    rows=_rows(manifest)
    metadata=json.loads((directory/'dataset.json').read_text())
    id=directory.name;batch=metadata['batch_id']
    old=db.conn.execute('SELECT * FROM datasets WHERE id=?',(id,)).fetchone()
    digest=hashlib.sha256(manifest.read_bytes()).hexdigest()
    expected=old['manifest_sha256'] if old else metadata.get('manifest_sha256',digest)
    batch_record=db.conn.execute('SELECT plan FROM batches WHERE id=?',(batch,)).fetchone()
    plan=json.loads(batch_record[0]) if batch_record else {}
    samples=db.conn.execute('SELECT verdict FROM qa_samples WHERE batch_id=?',(batch,)).fetchall()
    reviewed=[r[0] for r in samples if r[0] in ('accept','reject')]
    precision=reviewed.count('accept')/200 if len(reviewed)==200 else None
    licences=sorted({r.get('licence','') for r in rows})
    sources=sorted({r.get('source','') for r in rows})
    synthetic=bool(rows) and any(r.get('source_url','').startswith('stub://') for r in rows)
    reasons=[]
    if not rows:reasons.append('Empty dataset')
    if digest!=expected:reasons.append('Manifest SHA-256 changed')
    if any(not r.get('licence','').strip() or not r.get('attribution','').strip() for r in rows):
        reasons.append('Missing licence or attribution')
    if not set(licences)<=LICENCES:reasons.append('Unsupported licence')
    if not set(sources)<=SOURCES:reasons.append('Unsupported source')
    if any(not r.get('source_url','').strip() for r in rows):reasons.append('Missing source URL')
    if any(len(r.get('provenance_hash',''))!=64 for r in rows):reasons.append('Missing image provenance')
    if precision is None or precision<.90:reasons.append('QA approval missing or below 90%')
    if synthetic:reasons.append('Synthetic fixture; not for sale')
    if 'platform_public_as_is' in licences:
        reasons.append('Platform provenance does not grant resale rights; rights review required')
    attributions=[]
    for row in rows:
        extra=db.conn.execute('SELECT * FROM image_metadata WHERE row_id=?',(row.get('id',''),)).fetchone()
        attributions.append({
            'creator':row.get('attribution',''),'source_url':row.get('source_url',''),
            'licence':row.get('licence',''),
            'licence_url':extra['licence_url'] if extra else LICENCE_URLS.get(row.get('licence'),''),
            'title':extra['title'] if extra else '',
            'source_page_url':extra['source_page_url'] if extra else row.get('source_url',''),
        })
    attributions=list({json.dumps(record,sort_keys=True):record for record in attributions}.values())
    name=plan.get('prompt',batch)
    created=old['created_at'] if old else datetime.fromtimestamp(manifest.stat().st_mtime,timezone.utc).isoformat()
    record={'id':id,'batch_id':batch,'name':name,'description':name,
        'attribute':plan.get('attribute',name),'labels':json.dumps([plan.get('attribute',name)]),
        'manifest_path':str(manifest),'manifest_sha256':expected,
        'created_at':created,'row_count':len(rows),
        'size_bytes':sum(p.stat().st_size for p in directory.rglob('*') if p.is_file()),
        'train_count':sum(r.get('split')=='train' for r in rows),'validation_count':sum(r.get('split')=='validation' for r in rows),
        'sources':json.dumps(sources),'licences':json.dumps(licences),
        'attributions':json.dumps(attributions),'qa_precision':precision,'synthetic':int(synthetic),
        'saleable':int(not reasons),'unavailable_reason':'; '.join(reasons),'version':metadata.get('version','')}
    # Existing prices are retained. Legacy packages default to 0, never invented prices.
    with db.conn:
        updates=','.join(f'{key}=excluded.{key}' for key in record if key!='id')
        db.conn.execute('INSERT INTO datasets('+','.join(record)+') VALUES('+
            ','.join('?' for _ in record)+') ON CONFLICT(id) DO UPDATE SET '+updates,tuple(record.values()))
    return id

def sync_packages(db,destination):
    for manifest in sorted(Path(destination).glob('*/manifest.csv')):
        try:register_dataset(db,manifest.parent)
        except (OSError,ValueError,KeyError,csv.Error) as error:
            with db.conn:
                db.conn.execute('UPDATE datasets SET saleable=0,unavailable_reason=? WHERE id=?',
                                ('Package cannot be read: '+str(error),manifest.parent.name))

def _integrity(db):
    for row in db.conn.execute('SELECT id,manifest_path,manifest_sha256 FROM datasets WHERE saleable=1').fetchall():
        path=Path(row['manifest_path'])
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=row['manifest_sha256']:
            with db.conn:
                db.conn.execute("UPDATE datasets SET saleable=0,unavailable_reason='Manifest missing or SHA-256 changed' WHERE id=?",(row['id'],))

def _decode(row):
    result=dict(row)
    for field in ('labels','sources','licences','attributions'):
        result[field]=json.loads(result[field])
    result['price']=result['price_cents']/100
    result['prompt']=result['name']
    result['count']=result['row_count']
    result['train']=result['train_count']
    result['validation']=result['validation_count']
    result['sale_cleared']=bool(result['saleable'])
    result['provenance_hash']=result['manifest_sha256']
    result['synthetic']=bool(result['synthetic'])
    result['saleable']=bool(result['saleable'])
    result['attribution']=result['attributions']
    result.pop('manifest_path',None)
    return result

def search_datasets(db,params,include_unavailable=False):
    _integrity(db)
    clauses=[] if include_unavailable else ['saleable=1']
    args=[]
    for key,column in (('q','name'),('attribute','attribute')):
        value=str(params.get(key,'')).strip()
        if value:
            clauses.append(f"lower({column}) LIKE ? ESCAPE '\\'")
            escaped=value.lower().replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
            args.append('%'+escaped+'%')
    for key,column,allowed in (('licence','licences',LICENCES),('source','sources',SOURCES)):
        value=params.get(key)
        if value:
            if value not in allowed:raise ValueError('Unsupported '+key)
            clauses.append(f'EXISTS(SELECT 1 FROM json_each(datasets.{column}) WHERE value=?)')
            args.append(value)
    for name,column,op,scale in (
        ('min_size','row_count','>=',1),('max_size','row_count','<=',1),
        ('min_price','price_cents','>=',100),('max_price','price_cents','<=',100)):
        if params.get(name) not in (None,''):
            from decimal import Decimal, InvalidOperation
            try:value=Decimal(str(params[name]))*scale
            except InvalidOperation:raise ValueError('Invalid '+name)
            if not value.is_finite() or value<0 or value>9000000000000000 or value!=value.to_integral_value():
                raise ValueError('Invalid '+name)
            clauses.append(f'{column}{op}?');args.append(int(value))
    if str(params.get('free','')).lower() in ('true','1'):
        clauses.append('price_cents=0')
    sorts={'newest':'created_at DESC,id','largest':'row_count DESC,id',
           'price_low':'price_cents ASC,id','price_high':'price_cents DESC,id'}
    sort=params.get('sort','newest')
    if sort not in sorts:raise ValueError('Invalid sort')
    try:page=int(params.get('page',1));limit=int(params.get('limit',12))
    except (TypeError,ValueError):raise ValueError('Invalid pagination')
    if not 1<=page<=1000000 or not 1<=limit<=100:raise ValueError('Invalid pagination')
    where=' WHERE '+' AND '.join(clauses) if clauses else ''
    total=db.conn.execute('SELECT count(*) FROM datasets'+where,args).fetchone()[0]
    records=db.conn.execute('SELECT * FROM datasets'+where+' ORDER BY '+sorts[sort]+' LIMIT ? OFFSET ?',
                            (*args,limit,(page-1)*limit)).fetchall()
    return {'items':[_decode(r) for r in records],'total':total,'page':page,'limit':limit}

def dataset_detail(db,id,require_saleable=False):
    _integrity(db)
    row=db.conn.execute('SELECT * FROM datasets WHERE id=?',(id,)).fetchone()
    if not row:raise ValueError('Dataset not found')
    detail=_decode(row)
    if require_saleable and not detail['saleable']:
        raise ValueError('Dataset unavailable: '+detail['unavailable_reason'])
    directory=Path(row['manifest_path']).parent
    try:images=_rows(row['manifest_path'])
    except (OSError,ValueError,csv.Error):images=[]
    detail['train']=sum(r['split']=='train' for r in images)
    detail['validation']=sum(r['split']=='validation' for r in images)
    detail['samples']=[{'id':r['id'],'url':f'/api/asset?kind=sample&package={id}&id={r["id"]}',
        'licence':r['licence'],'attribution':r['attribution']}
        for r in images if detail['saleable'] and r.get('id') and r.get('qa_verdict')=='accept' and (directory/'images'/r['id']).is_file()][:12]
    detail['licence_links']=[{'licence':name,'url':next((r['licence_url'] for r in detail['attributions'] if r['licence']==name and r['licence_url']),LICENCE_URLS.get(name,''))} for name in detail['licences']]
    return detail

def set_price(db,id,price_cents):
    if type(price_cents) is not int or not 0<=price_cents<=100000000:
        raise ValueError('price_cents must be an integer between 0 and 100000000')
    dataset_detail(db,id,require_saleable=True)
    with db.conn:
        db.conn.execute('UPDATE datasets SET price_cents=? WHERE id=?',(price_cents,id))
    return {'price_cents':price_cents,'currency':'USD','price':price_cents/100}

def buyer_manifest(db,id):
    detail=dataset_detail(db,id,require_saleable=True)
    path=db.conn.execute('SELECT manifest_path FROM datasets WHERE id=?',(id,)).fetchone()[0]
    return {'dataset':detail,'licence':detail['licences'],'attribution':detail['attributions'],
            'provenance_hash':detail['manifest_sha256'],'hash_algorithm':'SHA-256',
            'hashed_file':'manifest.csv','qa_precision':detail['qa_precision'],'images':_rows(path)}

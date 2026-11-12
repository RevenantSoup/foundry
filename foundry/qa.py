"""Persistent 200-item review sample and labeled contact sheets."""
import csv
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps

def selected_rows(db,batch):
    record=db.conn.execute('SELECT plan FROM batches WHERE id=?',(batch,)).fetchone()
    if not record:
        raise ValueError('Unknown batch')
    target=json.loads(record[0])['target']
    return sorted((r for r in db.rows(batch) if r.vlm_verdict=='accept'),
                  key=lambda r:(-r.clip_score,r.id))[:target]

def sample_ids(db,batch):
    rows=selected_rows(db,batch)
    if len(rows)<200:
        raise ValueError(f'QA requires 200 distinct accepted images; found {len(rows)}')
    return [r.id for r in sorted(rows,key=lambda r:hashlib.sha256((batch+r.id).encode()).hexdigest())[:200]]

def create_sheet(db,batch,raw,destination):
    ids=sample_ids(db,batch)
    existing=[r[0] for r in db.conn.execute('SELECT row_id FROM qa_samples WHERE batch_id=? ORDER BY position',(batch,))]
    if existing and existing != ids:
        raise ValueError('QA sample changed; create a new batch')
    snapshots={}
    for id in ids:
        path=(Path(raw)/id).resolve()
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        saved=db.conn.execute('SELECT sha256 FROM qa_files WHERE batch_id=? AND row_id=?',(batch,id)).fetchone()
        if saved and saved[0]!=digest:
            raise ValueError(f'QA image bytes changed: {id}; create a new batch')
        snapshots[id]=(digest,str(path))
    with db.conn:
        for index,id in enumerate(ids):
            digest,path=snapshots[id]
            saved=db.conn.execute('SELECT 1 FROM qa_files WHERE batch_id=? AND row_id=?',(batch,id)).fetchone()
            if not saved:
                # Older databases have no byte snapshot: require a fresh review.
                db.conn.execute("UPDATE qa_samples SET verdict='' WHERE batch_id=? AND row_id=?",(batch,id))
                db.conn.execute("UPDATE rows SET qa_verdict='' WHERE id=?",(id,))
                db.conn.execute('UPDATE batches SET qa_passed=0 WHERE id=?',(batch,))
            db.conn.execute('INSERT OR IGNORE INTO qa_files VALUES(?,?,?,?)',(batch,id,digest,path))
            db.conn.execute('INSERT OR IGNORE INTO qa_samples(batch_id,row_id,position) VALUES(?,?,?)',(batch,id,index))
    destination=Path(destination); destination.mkdir(parents=True,exist_ok=True)
    sheet=Image.new('RGB',(1600,2880),'white')
    draw=ImageDraw.Draw(sheet)
    for index,id in enumerate(ids):
        x=(index%10)*160; y=(index//10)*144
        with Image.open(Path(raw)/id) as image:
            crop=ImageOps.fit(image.convert('RGB'),(160,120))
        crop.save(destination/f'{index:03d}-{id}.png')
        sheet.paste(crop,(x,y)); draw.text((x+2,y+122),id[:24],fill='black')
    path=destination/'contact-sheet.png'; sheet.save(path)
    template=destination/'verdicts.csv'
    if not template.exists():
        with template.open('w',newline='',encoding='utf-8') as f:
            writer=csv.writer(f); writer.writerow(['id','verdict'])
            writer.writerows((id,'') for id in ids)
    return path,template

def check_qa(db,batch,raw=None):
    expected=set(sample_ids(db,batch))
    reviewed={r['row_id']:r['verdict'] for r in db.conn.execute('SELECT * FROM qa_samples WHERE batch_id=?',(batch,))}
    if set(reviewed)!=expected or any(v not in ('accept','reject') for v in reviewed.values()):
        raise ValueError('QA incomplete: review all 200 samples')
    snapshots={r['row_id']:r for r in db.conn.execute('SELECT * FROM qa_files WHERE batch_id=?',(batch,))}
    if set(snapshots)!=expected:
        raise ValueError('QA has no image snapshots; regenerate the contact sheet and review')
    for id,snapshot in snapshots.items():
        path=Path(raw)/id if raw is not None else Path(snapshot['path'])
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=snapshot['sha256']:
            raise ValueError(f'QA image bytes changed: {id}; create a new batch')
    failing=sorted(id for id,v in reviewed.items() if v=='reject')
    precision=(200-len(failing))/200
    if precision < .90:
        raise ValueError(f'Precision {precision:.3f} < 0.90; failing IDs: '+', '.join(failing))
    return precision

def read_verdicts(db,batch,path):
    with Path(path).open(newline='',encoding='utf-8') as stream:
        records=list(csv.DictReader(stream))
    expected=set(sample_ids(db,batch))
    if len(records)!=200 or {r.get('id') for r in records}!=expected:
        raise ValueError('Verdicts must contain each of the 200 sampled IDs exactly once')
    if any(r.get('verdict') not in ('accept','reject') for r in records):
        raise ValueError('Every verdict must be accept or reject')
    actual={r[0] for r in db.conn.execute('SELECT row_id FROM qa_samples WHERE batch_id=?',(batch,))}
    if actual!=expected:
        raise ValueError('Generate the QA contact sheet before submitting verdicts')
    with db.conn:
        db.conn.execute('UPDATE batches SET qa_passed=0 WHERE id=?',(batch,))
        for row in records:
            db.conn.execute('UPDATE qa_samples SET verdict=? WHERE batch_id=? AND row_id=?',
                            (row['verdict'],batch,row['id']))
            db.conn.execute('UPDATE rows SET qa_verdict=? WHERE id=?',(row['verdict'],row['id']))
    precision=check_qa(db,batch)
    with db.conn:
        db.conn.execute('UPDATE batches SET qa_passed=1 WHERE id=?',(batch,))
    return precision

"""Normalized CLIP embeddings, deterministic offline embeddings, fixed cascade."""
import hashlib
import json
import os
from pathlib import Path
import numpy as np
from PIL import Image

class Embedder:
    def __init__(self, backend='stub'):
        self.backend = backend
        self.identity = "clip:clip-ViT-B-32:v1" if backend=="clip" else "stub:sha256-rng:v1"
        self.model = None
        if backend == 'clip':
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer('clip-ViT-B-32')
    def images(self, paths):
        if self.model:
            images=[]
            for path in paths:
                with Image.open(path) as im:
                    images.append(im.convert('RGB'))
            vectors=np.asarray(self.model.encode(images),dtype=np.float32)
        else:
            vectors=[]
            for path in paths:
                seed=int(hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16],16)
                v=np.random.default_rng(seed).normal(size=511)
                v=v/np.linalg.norm(v)*0.8
                vectors.append(np.r_[0.6,v])
            vectors=np.asarray(vectors,dtype=np.float32)
        return normalize(vectors)
    def query(self,prompt,refs):
        if self.model:
            text=normalize(np.asarray(self.model.encode([prompt]),dtype=np.float32))[0]
            if refs:
                text=0.5*text+0.5*self.images(refs).mean(axis=0)
            return normalize(text)
        return np.r_[1.,np.zeros(511)].astype(np.float32)

def normalize(vectors):
    return vectors/np.maximum(np.linalg.norm(vectors,axis=-1,keepdims=True),1e-12)

def top_k(vectors, query, k):
    scores=normalize(vectors) @ normalize(query)
    return [(int(i),float(scores[i])) for i in np.argsort(-scores,kind='stable')[:k]]

def filter_batch(db,batch,plan,raw,embedder,verifier,store):
    identity=getattr(embedder,'identity','custom:'+type(embedder).__name__)
    with db.conn:
        stored=db.conn.execute("SELECT value FROM app_state WHERE key='embedding_backend'").fetchone()
        if stored and stored[0]!=identity:
            raise ValueError('Embedding backend differs from this dataset root; use a separate --root')
        if not stored:
            if db.conn.execute('SELECT 1 FROM embeddings LIMIT 1').fetchone():
                raise ValueError('Existing embeddings have no backend identity; use a new --root')
            db.conn.execute("INSERT INTO app_state VALUES('embedding_backend',?)",(identity,))
    rows=db.rows(batch)
    if not rows:
        raise ValueError('Batch has no harvested rows')
    pending=[r for r in rows if not db.conn.execute('SELECT 1 FROM embeddings WHERE row_id=?',(r.id,)).fetchone()]
    if pending:
        vectors=embedder.images([Path(raw)/r.id for r in pending])
        with db.conn:
            for row,vec in zip(pending,vectors):
                db.conn.execute('INSERT INTO embeddings VALUES(?,?)',(row.id,np.asarray(vec,dtype=np.float32).tobytes()))
    # Persist the global embedding matrix and an explicit row-ID index.
    records=db.conn.execute('SELECT row_id,vector FROM embeddings ORDER BY row_id').fetchall()
    global_vectors=np.stack([np.frombuffer(r['vector'],dtype=np.float32) for r in records])
    store=Path(store); store.mkdir(parents=True,exist_ok=True)
    with (store/'embeddings.tmp').open('wb') as handle:
        np.save(handle,global_vectors)
    os.replace(store/'embeddings.tmp',store/'embeddings.npy')
    (store/'embeddings.ids.json').write_text(json.dumps([r['row_id'] for r in records]))
    lookup={r['row_id']:v for r,v in zip(records,global_vectors)}
    query=embedder.query(plan['prompt'],plan['refs'])
    # All rows receive scores before retrieval or verification.
    for row in rows:
        db.update(row.id,clip_score=float(lookup[row.id] @ query))
    previous=[r for r in db.rows() if r.batch_id != batch and r.vlm_verdict not in ('','duplicate')]
    seen=[lookup[r.id] for r in previous if r.id in lookup]
    eligible=[]
    for row in rows:
        vec=lookup[row.id]
        if seen and np.max(np.stack(seen) @ vec)>0.95:
            if row.vlm_verdict!='duplicate':
                with db.conn: db.drop(row,'cosine')
            db.update(row.id,vlm_verdict='duplicate')
        else:
            seen.append(vec)
            if float(vec @ query)>=plan['threshold']:
                eligible.append(row)
            elif not row.vlm_verdict:
                db.update(row.id,vlm_verdict='below_threshold')
    eligible.sort(key=lambda r:(-float(lookup[r.id] @ query),r.id))
    shortlist=eligible[:3*plan['target']]
    shortlisted={r.id for r in shortlist}
    for row in eligible:
        if row.id not in shortlisted and not row.vlm_verdict:
            db.update(row.id,vlm_verdict='not_shortlisted')
    for row in shortlist:
        if not row.vlm_verdict:
            verdict=verifier.verify(Path(raw)/row.id,plan['prompt'],plan['checklist'])
            if verdict not in ('accept','reject'):
                raise ValueError('Verifier must return accept or reject')
            db.update(row.id,vlm_verdict=verdict)
    return len(shortlist)

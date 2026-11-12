import numpy as np
from foundry.cascade.embed import Embedder, top_k, filter_batch
from foundry.cascade.verify import StubVerifier
from foundry.db import Database
from foundry.adapters.openverse import OpenverseAdapter
import imagehash
import io
from PIL import Image

def test_normalized_top_k(tmp_path):
    a = OpenverseAdapter()
    row = a.search('x',1)[0]
    path = tmp_path/row.id; path.write_bytes(a.fetch(row))
    embed = Embedder()
    vectors = embed.images([path])
    assert np.allclose(np.linalg.norm(vectors,axis=1),1)
    assert top_k(vectors,embed.query('x',[]),1)[0][0] == 0

def test_shortlist_only_and_resume(tmp_path):
    db = Database(tmp_path/'db')
    raw = tmp_path/'raw'; raw.mkdir()
    adapter = OpenverseAdapter()
    for row in adapter.search('x',20):
        payload=adapter.fetch(row); (raw/row.id).write_bytes(payload)
        row.phash=str(imagehash.phash(Image.open(io.BytesIO(payload))))
        row.batch_id='b'; db.insert(row)
    class Counting(StubVerifier):
        calls=0
        def verify(self,*args):
            self.calls+=1
            return super().verify(*args)
    verifier=Counting()
    plan={'prompt':'x','refs':[],'target':2,'threshold':0.28,'checklist':['x']}
    filter_batch(db,'b',plan,raw,Embedder(),verifier,tmp_path)
    assert verifier.calls == 6
    assert all(r.clip_score is not None for r in db.rows('b'))
    filter_batch(db,'b',plan,raw,Embedder(),verifier,tmp_path)
    assert verifier.calls == 6
    assert np.load(tmp_path/'embeddings.npy').shape[0] == 20

def test_cosine_duplicate_is_logged(tmp_path):
    from tests.test_db import row
    db=Database(tmp_path/'db')
    a=row(batch_id='b'); b=row('b',batch_id='b')
    b.phash='ffffffffffffffff'
    db.insert(a); db.insert(b)
    raw=tmp_path/'raw'; raw.mkdir()
    raw.joinpath(a.id).write_bytes(b'a'); raw.joinpath(b.id).write_bytes(b'b')
    class Identical:
        def images(self,paths): return np.array([[1.,0.]]*len(paths))
        def query(self,*args): return np.array([1.,0.])
    filter_batch(db,'b',{'prompt':'x','refs':[],'target':1,'threshold':0.,'checklist':[]},
                 raw,Identical(),StubVerifier(),tmp_path)
    assert db.conn.execute("select count(*) from drops where reason='cosine'").fetchone()[0]==1

def test_embedding_backend_cannot_change(tmp_path):
    db=Database(tmp_path/'db')
    from tests.test_db import row
    r=row(batch_id='b'); db.insert(r)
    raw=tmp_path/'raw'; raw.mkdir(); (raw/r.id).write_bytes(b'fixture')
    class Backend:
        identity='backend-a'
        def images(self,paths): return np.array([[1.,0.]]*len(paths),dtype=np.float32)
        def query(self,*args): return np.array([1.,0.])
    plan={'prompt':'x','refs':[],'target':1,'threshold':0.,'checklist':[]}
    backend=Backend()
    filter_batch(db,'b',plan,raw,backend,StubVerifier(),tmp_path)
    backend.identity='backend-b'
    import pytest
    with pytest.raises(ValueError,match='backend'):
        filter_batch(db,'b',plan,raw,backend,StubVerifier(),tmp_path)

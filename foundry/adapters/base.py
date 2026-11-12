"""Source contract plus deterministic, explicitly synthetic offline fixtures."""
from abc import ABC, abstractmethod
import hashlib
import io
import numpy as np
from PIL import Image
from ..models import Row

class Adapter(ABC):
    @abstractmethod
    def search(self, q, limit): ...
    @abstractmethod
    def fetch(self, row): ...
    @abstractmethod
    def licence(self, row): ...

def fixture_rows(source, q, limit, licence):
    return [Row(id=hashlib.sha256(f'{source}:{q}:{i}'.encode()).hexdigest()[:24],
                source=source, source_url=f'stub://{source}/{hashlib.sha256(q.encode()).hexdigest()[:12]}/{i}',
                licence=licence, attribution='Foundry synthetic offline fixture (not source media)',
                frame_ts_ms=(i+2)*1000 if source=='youtube' else 0)
            for i in range(limit)]

def fixture_bytes(row):
    seed = int(hashlib.sha256(row.id.encode()).hexdigest()[:16],16)
    rng = np.random.default_rng(seed)
    pixels = rng.integers(0,256,(16,16,3),dtype=np.uint8)
    image = Image.fromarray(pixels).resize((256,256),Image.Resampling.NEAREST)
    buffer = io.BytesIO()
    image.save(buffer,format='PNG')
    return buffer.getvalue()

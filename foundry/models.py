"""Dataset records and strict manifest serialization."""
import csv
from dataclasses import dataclass, asdict, fields
from pathlib import Path

@dataclass
class Row:
    id: str
    source: str
    source_url: str
    licence: str
    attribution: str
    captured_at: str = ''
    frame_ts_ms: int = 0
    phash: str = ''
    clip_score: float | None = None
    vlm_verdict: str = ''
    qa_verdict: str = ''
    split: str = ''
    batch_id: str = ''
    provenance_hash: str = ''

def validate_rights(row):
    if not row.licence or not row.licence.strip() or not row.attribution or not row.attribution.strip():
        raise ValueError(f'Missing licence or attribution: {row.id}')

def write_manifest(path, rows):
    rows = list(rows)
    for row in rows:
        validate_rights(row)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=[f.name for f in fields(Row)])
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)

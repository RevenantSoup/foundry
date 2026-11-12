"""SQLite state. One connection is owned by each Database instance."""
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from .models import Row, validate_rights

class Database:
    def __init__(self, path):
        self.conn = sqlite3.connect(path, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS rows (
          id TEXT PRIMARY KEY, source TEXT, source_url TEXT,
          licence TEXT NOT NULL CHECK(length(trim(licence))>0),
          attribution TEXT NOT NULL CHECK(length(trim(attribution))>0),
          captured_at TEXT, frame_ts_ms INT, phash TEXT NOT NULL,
          clip_score REAL, vlm_verdict TEXT, qa_verdict TEXT, split TEXT,
          batch_id TEXT, provenance_hash TEXT);
        CREATE TABLE IF NOT EXISTS seen_urls(url TEXT PRIMARY KEY, row_id TEXT);
        CREATE TABLE IF NOT EXISTS drops(id INTEGER PRIMARY KEY, row_id TEXT, batch_id TEXT, reason TEXT);
        CREATE TABLE IF NOT EXISTS batches(id TEXT PRIMARY KEY, plan TEXT NOT NULL, qa_passed INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS quota(source TEXT, day TEXT, units INTEGER NOT NULL, PRIMARY KEY(source,day));
        CREATE TABLE IF NOT EXISTS qa_samples(batch_id TEXT, row_id TEXT, position INT,
          verdict TEXT DEFAULT '', PRIMARY KEY(batch_id,row_id));
        CREATE TABLE IF NOT EXISTS embeddings(row_id TEXT PRIMARY KEY, vector BLOB NOT NULL);
        CREATE TABLE IF NOT EXISTS app_state(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        PRAGMA user_version=2;
        """)
    def close(self):
        self.conn.close()
    def rows(self, batch=None):
        sql = 'SELECT * FROM rows'
        args = ()
        if batch is not None:
            sql += ' WHERE batch_id=?'; args = (batch,)
        return [Row(**dict(r)) for r in self.conn.execute(sql+' ORDER BY id', args)]
    def drop(self, row, reason):
        self.conn.execute('INSERT INTO drops(row_id,batch_id,reason) VALUES(?,?,?)',
                          (row.id,row.batch_id,reason))
    def insert(self, row):
        validate_rights(row)
        with self.conn:
            if self.conn.execute('SELECT 1 FROM seen_urls WHERE url=?', (row.source_url,)).fetchone():
                self.drop(row,'seen_url')
                return False
            self.conn.execute('INSERT INTO seen_urls VALUES(?,?)',(row.source_url,row.id))
            for old in self.conn.execute('SELECT phash FROM rows'):
                if (int(old[0],16) ^ int(row.phash,16)).bit_count() <= 10:
                    self.drop(row,'phash')
                    return False
            if not row.captured_at:
                row.captured_at = datetime.now(timezone.utc).isoformat()
            data = asdict(row)
            self.conn.execute('INSERT INTO rows VALUES('+','.join('?' for _ in data)+')', tuple(data.values()))
        return True
    def update(self, id, **changes):
        allowed = set(Row.__dataclass_fields__) - {'id'}
        if not changes or not set(changes) <= allowed:
            raise ValueError('Invalid row update')
        with self.conn:
            self.conn.execute('UPDATE rows SET '+','.join(k+'=?' for k in changes)+' WHERE id=?',
                              (*changes.values(),id))

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
        CREATE TABLE IF NOT EXISTS qa_files(batch_id TEXT, row_id TEXT, sha256 TEXT NOT NULL,
          path TEXT NOT NULL, PRIMARY KEY(batch_id,row_id));

        CREATE TABLE IF NOT EXISTS image_metadata(
          row_id TEXT PRIMARY KEY, licence_url TEXT, creator TEXT, title TEXT, source_page_url TEXT);
        CREATE TABLE IF NOT EXISTS usage_log(
          id INTEGER PRIMARY KEY, source TEXT NOT NULL, batch_id TEXT, day TEXT NOT NULL,
          created_at TEXT NOT NULL, event TEXT NOT NULL DEFAULT 'request',
          status_code INTEGER, retry_count INTEGER DEFAULT 0, latency_ms REAL DEFAULT 0,
          is_error INTEGER DEFAULT 0, token_count INTEGER, cost_usd REAL, detail TEXT);
        CREATE INDEX IF NOT EXISTS usage_day ON usage_log(source,day);
        CREATE TABLE IF NOT EXISTS quota_blocks(
          source TEXT, day TEXT, reason TEXT, PRIMARY KEY(source,day));
        CREATE TABLE IF NOT EXISTS datasets(
          id TEXT PRIMARY KEY, batch_id TEXT NOT NULL, name TEXT NOT NULL,
          description TEXT NOT NULL, attribute TEXT NOT NULL, labels TEXT NOT NULL DEFAULT '[]',
          manifest_path TEXT NOT NULL, manifest_sha256 TEXT NOT NULL,
          price_cents INTEGER NOT NULL DEFAULT 0 CHECK(price_cents>=0),
          currency TEXT NOT NULL DEFAULT 'USD', created_at TEXT NOT NULL,
          row_count INTEGER NOT NULL, size_bytes INTEGER NOT NULL,
          train_count INTEGER NOT NULL DEFAULT 0, validation_count INTEGER NOT NULL DEFAULT 0,
          sources TEXT NOT NULL, licences TEXT NOT NULL, attributions TEXT NOT NULL,
          qa_precision REAL, synthetic INTEGER NOT NULL DEFAULT 0,
          saleable INTEGER NOT NULL DEFAULT 0, unavailable_reason TEXT NOT NULL DEFAULT '',
          version TEXT NOT NULL DEFAULT '');
        CREATE INDEX IF NOT EXISTS dataset_discovery ON datasets(saleable,created_at);
        CREATE TABLE IF NOT EXISTS schedules(
          id TEXT PRIMARY KEY, spec_path TEXT NOT NULL, interval TEXT NOT NULL,
          next_run_at TEXT NOT NULL, last_run_at TEXT, batch_id TEXT,
          enabled INTEGER NOT NULL DEFAULT 1, run_time TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending', last_error TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS schedule_log(
          id INTEGER PRIMARY KEY, schedule_id TEXT, created_at TEXT, event TEXT, detail TEXT);
        CREATE TABLE IF NOT EXISTS api_keys(
          id TEXT PRIMARY KEY, key_hash TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
          created_at TEXT NOT NULL, last_used_at TEXT, revoked_at TEXT, is_active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS api_rate_limits(
          key_id TEXT, window_start INTEGER, requests INTEGER NOT NULL,
          PRIMARY KEY(key_id,window_start));
        CREATE TABLE IF NOT EXISTS orders(
          id TEXT PRIMARY KEY, dataset_id TEXT NOT NULL, buyer_email TEXT NOT NULL,
          stripe_session_id TEXT UNIQUE, amount INTEGER NOT NULL, currency TEXT NOT NULL,
          status TEXT NOT NULL, buyer_key_id TEXT NOT NULL, idempotency_key TEXT,
          fingerprint TEXT NOT NULL, manifest_sha256 TEXT NOT NULL, stripe_payment_id TEXT,
          created_at INTEGER NOT NULL, UNIQUE(buyer_key_id,idempotency_key));
        CREATE TABLE IF NOT EXISTS download_grants(
          order_id TEXT PRIMARY KEY, nonce TEXT NOT NULL, expires_at INTEGER NOT NULL);
        PRAGMA user_version=4;
        """)
        columns={r[1] for r in self.conn.execute('PRAGMA table_info(datasets)')}
        for name in ('train_count','validation_count'):
            if name not in columns:
                self.conn.execute(f'ALTER TABLE datasets ADD COLUMN {name} INTEGER NOT NULL DEFAULT 0')
        self.conn.execute('PRAGMA user_version=6')
        self.conn.commit()
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
            metadata = getattr(row,'metadata',{})
            if metadata:
                self.conn.execute('INSERT OR REPLACE INTO image_metadata VALUES(?,?,?,?,?)',
                    (row.id, metadata.get('licence_url',''),metadata.get('creator',row.attribution),
                     metadata.get('title',''),metadata.get('source_page_url',row.source_url)))
        return True
    def update(self, id, **changes):
        allowed = set(Row.__dataclass_fields__) - {'id'}
        if not changes or not set(changes) <= allowed:
            raise ValueError('Invalid row update')
        with self.conn:
            self.conn.execute('UPDATE rows SET '+','.join(k+'=?' for k in changes)+' WHERE id=?',
                              (*changes.values(),id))

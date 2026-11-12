"""Atomic UTC daily quotas, charged before every API request attempt."""
from datetime import datetime, timezone, timedelta
import click

class QuotaExceeded(click.ClickException):
    exit_code=2

def quota_status(db,source,limit=10000):
    now=datetime.now(timezone.utc);day=now.date().isoformat()
    row=db.conn.execute('SELECT units FROM quota WHERE source=? AND day=?',(source,day)).fetchone()
    used=row[0] if row else 0
    blocked=db.conn.execute('SELECT reason FROM quota_blocks WHERE source=? AND day=?',(source,day)).fetchone()
    return {'used':used,'remaining':0 if blocked else max(0,limit-used),
            'reset_at':datetime.combine(now.date()+timedelta(days=1),datetime.min.time(),tzinfo=timezone.utc).isoformat(),
            'provider_blocked':bool(blocked)}

def block_provider(db,source,reason):
    if db is not None:
        with db.conn:
            db.conn.execute('INSERT OR REPLACE INTO quota_blocks VALUES(?,?,?)',
                (source,datetime.now(timezone.utc).date().isoformat(),reason))

def consume(db,source,units,limit=10000):
    if units<0:
        raise ValueError('Negative quota charge')
    day=datetime.now(timezone.utc).date().isoformat()
    with db.conn:
        db.conn.execute('BEGIN IMMEDIATE')
        db.conn.execute('INSERT OR IGNORE INTO quota VALUES(?,?,0)',(source,day))
        status=quota_status(db,source,limit)
        if status['provider_blocked'] or status['used']+units>limit:
            raise QuotaExceeded(f"{source} daily quota exhausted: used {status['used']} / {limit}; "
                f"remaining {status['remaining']}; requested {units}; resets {status['reset_at']}")
        db.conn.execute('UPDATE quota SET units=units+? WHERE source=? AND day=?',(units,source,day))

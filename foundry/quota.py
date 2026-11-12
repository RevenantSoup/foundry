"""Atomic UTC daily quotas, charged before making API calls."""
from datetime import datetime, timezone
import click

class QuotaExceeded(click.ClickException):
    exit_code = 2

def consume(db, source, units, limit=10000):
    if units < 0:
        raise ValueError('Negative quota charge')
    day = datetime.now(timezone.utc).date().isoformat()
    with db.conn:
        db.conn.execute('BEGIN IMMEDIATE')
        db.conn.execute('INSERT OR IGNORE INTO quota VALUES(?,?,0)',(source,day))
        used = db.conn.execute('SELECT units FROM quota WHERE source=? AND day=?',(source,day)).fetchone()[0]
        if used + units > limit:
            raise QuotaExceeded(f'{source} daily quota exhausted: {used}+{units}>{limit}')
        db.conn.execute('UPDATE quota SET units=units+? WHERE source=? AND day=?',(units,source,day))

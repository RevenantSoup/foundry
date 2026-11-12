"""Append-only provider/buyer usage. Never store credentials or raw request URLs."""
from datetime import datetime, timezone

def log_usage(db, source, batch_id='', **values):
    if db is None:
        return
    now=datetime.now(timezone.utc)
    data={'source':source,'batch_id':batch_id,'day':now.date().isoformat(),
          'created_at':now.isoformat(),**values}
    with db.conn:
        db.conn.execute('INSERT INTO usage_log('+','.join(data)+') VALUES('+','.join('?' for _ in data)+')',tuple(data.values()))

def daily_usage(db):
    return [dict(r) for r in db.conn.execute("""
      SELECT source,day,
        sum(CASE WHEN event='request' THEN 1 ELSE 0 END) AS requests,
        sum(CASE WHEN status_code=429 THEN 1 ELSE 0 END) AS rate_limits,
        sum(is_error) AS errors,
        sum(CASE WHEN event='request' AND retry_count>0 THEN 1 ELSE 0 END) AS retries,
        sum(latency_ms) AS latency_ms, sum(token_count) AS tokens, sum(cost_usd) AS cost_usd
      FROM usage_log GROUP BY source,day ORDER BY day,source""")]

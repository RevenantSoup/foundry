"""Structured operational events with secret redaction and opt-in monitoring."""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import sys

def redact(message):
    for name in ('YOUTUBE_API_KEY','OPENAI_API_KEY','OPENVERSE_API_KEY','FOUNDRY_ADMIN_PASSWORD','FOUNDRY_SESSION_SECRET','SENTRY_DSN'):
        value=os.environ.get(name)
        if value:message=message.replace(value,'[redacted]')
    message=re.sub(r'Bearer\s+[^\s"\']+','Bearer [redacted]',message,flags=re.I)
    return re.sub(r'fdy_[A-Za-z0-9_-]+','[buyer-key-redacted]',message)

def event(level,command,batch_id='',message='',**fields):
    record={'timestamp':datetime.now(timezone.utc).isoformat(),'level':level,
            'command':command,'batch_id':batch_id,'message':redact(str(message)),**fields}
    line=redact(json.dumps(record))
    print(line,file=sys.stderr)
    destination=os.environ.get('FOUNDRY_LOG_FILE')
    if destination:
        try:
            path=Path(destination);path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('a',encoding='utf-8') as stream:stream.write(line+'\n')
        except OSError:
            fallback={**record,'level':'error','message':'Configured log file unavailable'}
            print(redact(json.dumps(fallback)),file=sys.stderr)
    if level=='error' and os.environ.get('SENTRY_DSN'):
        try:
            import sentry_sdk
            if not sentry_sdk.is_initialized():sentry_sdk.init(dsn=os.environ['SENTRY_DSN'],default_integrations=False,send_default_pii=False)
            sentry_sdk.capture_message(record['message'],level='error')
        except Exception:
            pass

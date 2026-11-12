"""Bounded provider HTTP policy: initial call plus at most three retries."""
import time
import requests
from .usage import log_usage
from .quota import QuotaExceeded, block_provider

def request_with_retry(session,method,url,*,db=None,source='',batch_id='',charge=None,
                       sleep=None,**kwargs):
    sleep=sleep or time.sleep
    kwargs.setdefault('timeout',30)
    for attempt in range(4):
        if charge:
            charge()  # Every actual YouTube attempt consumes quota, including retries.
        started=time.monotonic()
        response=None
        try:
            response=getattr(session,method)(url,**kwargs)
            status=response.status_code
            log_usage(db,source,batch_id,status_code=status,retry_count=attempt,
                      latency_ms=(time.monotonic()-started)*1000,is_error=int(status>=400))
            if source=='youtube' and status==403:
                try:
                    reasons={item.get('reason') for item in response.json().get('error',{}).get('errors',[])}
                except (ValueError,AttributeError,TypeError):
                    reasons=set()
                if reasons & {'quotaExceeded','dailyLimitExceeded'}:
                    block_provider(db,'youtube','YouTube reported quotaExceeded')
                    raise QuotaExceeded('YouTube provider quota exhausted; '+quota_message(db))
            response.raise_for_status()
            return response
        except (requests.Timeout,requests.ConnectionError):
            log_usage(db,source,batch_id,retry_count=attempt,
                      latency_ms=(time.monotonic()-started)*1000,is_error=1,detail='network_error')
            if attempt==3:
                raise requests.ConnectionError(f'{source or "Provider"} network request failed after 3 retries') from None
        except requests.HTTPError:
            if response is None or (response.status_code!=429 and response.status_code<500) or attempt==3:
                status=response.status_code if response is not None else 'error'
                raise requests.HTTPError(f'{source or "Provider"} HTTP {status}; request failed after {attempt} retries',response=response) from None
        if response is not None:
            response.close() if hasattr(response,'close') else None
        sleep(2**attempt)
    raise RuntimeError('Unreachable retry state')

def quota_message(db):
    from .quota import quota_status
    status=quota_status(db,'youtube')
    return f"used {status['used']} / 10000; remaining {status['remaining']}; resets {status['reset_at']}"

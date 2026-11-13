"""Authenticated internal worker transport. Never publish this port without TLS."""
from __future__ import annotations

import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shutil
import threading
from urllib.parse import urlsplit

from web import bridge
from .logging import event

MAX_BODY = 86 * 1024 * 1024
MODES = frozenset(('state', 'batch', 'plan', 'refs_plan', 'price', 'seo', 'health',
                   'demo', 'usage', 'discovery', 'dataset', 'buyer', 'payments'))


def configured_key():
    key = os.environ.get('FOUNDRY_WORKER_API_KEY', '')
    if len(key) < 32 or re.match(r'^(fdy_|replace|change|<)', key, re.I) or any(word in key.lower() for word in
            ('placeholder', 'change-me', 'changeme', 'replace-me', 'your-worker')):
        return None
    return key


def scrub(value):
    """Compute server-private replacements once per response, then scrub recursively."""
    replacements = [(secret, '[redacted]') for name, secret in os.environ.items()
                    if secret and len(secret) >= 8 and any(part in name for part in
                    ('SECRET', 'API_KEY', 'PASSWORD', 'TOKEN', 'FOUNDRY_WORKER_URL'))]
    replacements += [(str(bridge.root()), '[storage]'), (str(bridge.REPO), '[storage]')]

    def clean(item):
        if isinstance(item, dict):
            return {key: clean(value) for key, value in item.items()}
        if isinstance(item, list):
            return [clean(value) for value in item]
        if isinstance(item, str):
            for secret, replacement in replacements:
                item = item.replace(secret, replacement)
        return item
    return clean(value)


class WorkerServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    _slots = threading.BoundedSemaphore(16)

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()


class Handler(BaseHTTPRequestHandler):
    server_version = 'FoundryWorker'
    sys_version = ''

    def __getattr__(self, name):
        if name.startswith('do_'):
            return self.unsupported_method
        raise AttributeError(name)

    def unsupported_method(self):
        if self.authorized():
            self.error(405, 'method_not_allowed', 'Worker supports GET and POST only')

    def setup(self):
        super().setup()
        self.connection.settimeout(125)

    def log_message(self, *_args):
        # Access logs must never contain signed tokens, request bodies, or keys.
        pass

    def send_json(self, status, body):
        data = json.dumps(scrub(body)).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def error(self, status, code, message):
        self.send_json(status, {'error': code, 'message': message})

    def authorized(self):
        expected = configured_key()
        supplied = self.headers.get('Authorization', '')
        if not expected or not hmac.compare_digest(supplied.encode(), ('Bearer ' + expected).encode()):
            self.error(401, 'unauthorized', 'Invalid worker credentials')
            return False
        return True

    def read_payload(self):
        if self.headers.get('Transfer-Encoding'):
            raise ValueError('Chunked requests are not supported')
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            raise ValueError('Invalid content length') from None
        if not 0 < length <= MAX_BODY:
            raise ValueError('Request body exceeds the limit or is empty')
        raw = self.rfile.read(length)
        if len(raw) != length:
            raise ValueError('Incomplete request body')
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError('Expected a JSON object')
        return result

    def stream_asset(self, metadata):
        path = Path(metadata['path']).resolve()
        if not path.is_relative_to(bridge.root()) or not path.is_file():
            raise ValueError('Invalid asset')
        filename = re.sub(r'[^a-zA-Z0-9_.-]', '_', metadata.get('filename', path.name))
        with path.open('rb') as source:
            self.send_response(200)
            self.send_header('Content-Type', metadata.get('mime', 'application/octet-stream'))
            disposition = 'inline' if metadata.get('mime', '').startswith('image/') else 'attachment'
            self.send_header('Content-Disposition', f'{disposition}; filename="{filename}"')
            self.send_header('Content-Length', str(path.stat().st_size))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            shutil.copyfileobj(source, self.wfile, length=64 * 1024)

    def unsupported_method(self):
        if self.authorized():
            self.error(405, 'method_not_allowed', 'Worker method is not supported')

    do_PUT = unsupported_method
    do_PATCH = unsupported_method
    do_DELETE = unsupported_method
    do_OPTIONS = unsupported_method
    do_HEAD = unsupported_method
    do_TRACE = unsupported_method
    do_CONNECT = unsupported_method

    def do_GET(self):
        if not self.authorized():
            return
        path = urlsplit(self.path).path
        try:
            if path == '/health':
                self.send_json(200, {'status': 'ok', **bridge.health_payload(),
                                     'version': os.environ.get('APP_VERSION', '0.1.0')})
            elif path.startswith('/jobs/'):
                self.send_json(200, bridge.job_status(path.removeprefix('/jobs/')))
            else:
                self.error(404, 'not_found', 'Unknown worker operation')
        except FileNotFoundError:
            self.error(404, 'not_found', 'Job not found')
        except (ValueError, KeyError):
            self.error(400, 'invalid_request', 'Invalid worker request')
        except Exception as error:
            event('error','worker',message='Worker operation failed: '+str(error))
            self.error(503, 'worker_unavailable', 'Worker operation failed; retry or inspect worker logs')

    def do_POST(self):
        if not self.authorized():
            return
        try:
            payload = self.read_payload()
            path = urlsplit(self.path).path
            if path == '/bridge':
                mode = payload.get('mode')
                body = payload.get('payload', {})
                if mode not in MODES or not isinstance(body, dict):
                    raise ValueError('Invalid operation')
                if mode == 'payments' and body.get('op') == 'download':
                    raise ValueError('Use the binary asset endpoint')
                self.send_json(200, bridge.invoke(mode, body))
            elif path == '/jobs':
                self.send_json(202, bridge.start_job(payload.get('batch'), payload.get('action'), payload.get('payload', {})))
            elif path == '/assets':
                self.stream_asset(bridge.asset(payload))
            elif path == '/paid-assets':
                result = bridge.payments_payload({**payload, 'op': 'download'})
                if result['status'] != 200:
                    self.send_json(result['status'], result['body'])
                else:
                    self.stream_asset(result['body'])
            else:
                self.error(404, 'not_found', 'Unknown worker operation')
        except (ValueError, KeyError, TypeError):
            self.error(400, 'invalid_request', 'Invalid worker request')
        except FileNotFoundError:
            self.error(404, 'not_found', 'Requested asset was not found')
        except BlockingIOError:
            self.error(409, 'worker_busy', 'Another pipeline job is running')
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as error:
            event('error','worker',message='Worker operation failed: '+str(error))
            self.error(503, 'worker_unavailable', 'Worker operation failed; retry or inspect worker logs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    if not configured_key():
        parser.error('FOUNDRY_WORKER_API_KEY must contain a separate strong worker credential (32+ characters)')
    WorkerServer((args.host, args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()

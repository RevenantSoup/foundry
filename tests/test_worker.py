import base64
from io import BytesIO
import json
import secrets
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from PIL import Image
import pytest

from foundry import worker
from web import bridge


@pytest.fixture
def worker_server(tmp_path, monkeypatch):
    key = secrets.token_hex(24)
    monkeypatch.setenv('FOUNDRY_ROOT', str(tmp_path))
    monkeypatch.setenv('FOUNDRY_WORKER_API_KEY', key)
    server = worker.WorkerServer(('127.0.0.1', 0), worker.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    def request(path, payload=None, token=key, method=None):
        data = None if payload is None else json.dumps(payload).encode()
        headers = {'Content-Type': 'application/json'}
        if token is not None:
            headers['Authorization'] = 'Bearer ' + token
        req = Request(f'http://127.0.0.1:{server.server_port}{path}', data=data, headers=headers, method=method)
        try:
            response = urlopen(req, timeout=15)
        except HTTPError as error:
            response = error
        with response:
            return response.status, response.read(), response.headers
    yield request
    server.shutdown()
    server.server_close()
    thread.join()


def test_worker_health_authentication(worker_server):
    for token in (None, 'wrong', 'fdy_' + secrets.token_hex(24)):
        status, body, _ = worker_server('/health', token=token)
        assert status == 401 and json.loads(body)['error'] == 'unauthorized'
    status, body, _ = worker_server('/health')
    assert status == 200 and json.loads(body)['db'] == 'ok'


def test_worker_fail_closed_configuration(monkeypatch):
    for key in ('', 'short', 'fdy_' + secrets.token_hex(32), 'placeholder-' * 8):
        monkeypatch.setenv('FOUNDRY_WORKER_API_KEY', key)
        assert worker.configured_key() is None


def test_operation_allowlist_and_private_assets(worker_server):
    for mode, payload in [('seed', {}), ('job', {}), ('asset', {}), ('payments', {'op': 'download'})]:
        status, body, _ = worker_server('/bridge', {'mode': mode, 'payload': payload})
        assert status == 400 and b'path' not in body
    assert worker_server('/bridge', {'mode': 'state', 'payload': {}})[0] == 200
    assert worker_server('/assets', {'kind': 'manifest', 'package': '../escape'})[0] == 400
    assert worker_server('/jobs', {'batch': '../escape', 'action': 'harvest'})[0] == 400
    assert worker_server('/jobs/missing')[0] == 404


def test_stream_only_binary_metadata_stays_private(worker_server, tmp_path, monkeypatch):
    source = tmp_path / 'download.csv'
    source.write_text('id,licence\nx,CC0\n')
    monkeypatch.setattr(bridge, 'asset', lambda payload: {'path': str(source), 'mime': 'text/csv', 'filename': 'data.csv'})
    status, body, headers = worker_server('/assets', {'kind': 'manifest'})
    assert status == 200 and body == source.read_bytes()
    assert headers['Content-Type'] == 'text/csv'
    assert str(tmp_path).encode() not in body


def test_paid_asset_denials_preserve_status(worker_server, monkeypatch):
    for status in (403, 410):
        monkeypatch.setattr(bridge, 'payments_payload', lambda payload: {'status': status, 'body': {'error': 'access_denied'}})
        result, body, _ = worker_server('/paid-assets', {'token': 'untrusted'})
        assert result == status and json.loads(body)['error'] == 'access_denied'


def test_job_status_removes_private_payload(worker_server, tmp_path, monkeypatch):
    secret = secrets.token_hex(24)
    monkeypatch.setenv('STRIPE_WEBHOOK_SECRET', secret)
    bridge.atomic(tmp_path / 'web/jobs/job.json', {
        'id': 'job', 'status': 'succeeded', 'payload': {'secret': secret},
        'log': f'Wrote {tmp_path}/package.csv {secret}', 'exit_code': 0})
    status, body, _ = worker_server('/jobs/job')
    result = json.loads(body)
    assert status == 200 and result['exit_code'] == 0
    assert 'payload' not in result and str(tmp_path).encode() not in body and secret.encode() not in body


def test_worker_limits_and_invalid_json_shape(worker_server, monkeypatch):
    monkeypatch.setattr(worker, 'MAX_BODY', 12)
    assert worker_server('/bridge', {'mode': 'state'})[0] == 400
    assert worker_server('/bridge', [1])[0] == 400


def test_remote_plan_real_cli_and_job_submission(worker_server, tmp_path, monkeypatch):
    stream = BytesIO()
    Image.new('RGB', (20, 20), 'red').save(stream, format='PNG')
    refs = [{'name': '../../untrusted.png', 'data': base64.b64encode(stream.getvalue()).decode()} for _ in range(6)]
    status, raw, _ = worker_server('/bridge', {'mode': 'refs_plan', 'payload': {'prompt': 'people in safety glasses', 'refs': refs}})
    result = json.loads(raw)
    assert status == 200, result
    batch = result['batch']['id'] if 'batch' in result else result['id']
    # Execute the actual durable detached job and poll its stored state.
    status, raw, _ = worker_server('/jobs', {'batch': batch, 'action': 'harvest', 'payload': {}})
    job = json.loads(raw)
    assert status == 202 and job['status'] == 'queued'
    import time
    for _ in range(150):
        _, raw, _ = worker_server('/jobs/' + job['id'])
        state = json.loads(raw)
        if state['status'] in ('succeeded', 'failed'):
            break
        time.sleep(.1)
    assert state['status'] == 'succeeded', state
    status, raw, _ = worker_server('/jobs', {'batch': batch, 'action': 'filter', 'payload': {}})
    assert status == 202
    filter_id = json.loads(raw)['id']
    for _ in range(200):
        _, raw, _ = worker_server('/jobs/' + filter_id)
        state = json.loads(raw)
        if state['status'] in ('succeeded', 'failed'):
            break
        time.sleep(.1)
    assert state['status'] == 'succeeded', state
    assert not (tmp_path / 'untrusted.png').exists()


def test_reference_validation_before_files_created(tmp_path, monkeypatch):
    monkeypatch.setenv('FOUNDRY_ROOT', str(tmp_path))
    for refs in ([], [{'data': 'bad!'}] * 6, [{'data': base64.b64encode(b'not an image').decode()}] * 6):
        with pytest.raises(ValueError):
            bridge.refs_plan({'refs': refs, 'prompt': 'test'})
    assert not (tmp_path / 'web/refs').exists()


def test_all_worker_methods_require_authentication(worker_server):
    for method in ('HEAD','PUT','PATCH','DELETE','OPTIONS','BREW'):
        assert worker_server('/health',token=None,method=method)[0]==401
        assert worker_server('/health',method=method)[0]==405

"""Test-only hosted checkout. Grants expire 24 hours after verified payment.

Only explicitly selected Stripe identifiers are persisted, never event or card data.
File metadata returned here is internal: HTTP adapters must stream it, not serialize it.
"""
import base64
import csv
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import re
import secrets
import time
from urllib.parse import urlparse
import uuid
import zipfile

import stripe
from .buyers import authorize
from .marketplace import dataset_detail

IDENTIFIER = re.compile(r'^[a-zA-Z0-9_-]{1,100}$')
TTL = 24 * 60 * 60


def response(status_code, **body):
    if status_code >= 400 and 'message' not in body:
        body['message'] = body.get('error', 'request_failed').replace('_', ' ').capitalize()
    return {'status': status_code, 'body': body, 'headers': {'Cache-Control': 'no-store'}}


def config():
    values = {k: os.environ.get(k, '') for k in (
        'STRIPE_SECRET_KEY', 'STRIPE_PUBLISHABLE_KEY', 'STRIPE_WEBHOOK_SECRET',
        'FOUNDRY_DOWNLOAD_SECRET', 'STRIPE_SUCCESS_URL', 'STRIPE_CANCEL_URL')}
    for name, prefix in (('STRIPE_SECRET_KEY', 'sk_test_'),
                         ('STRIPE_PUBLISHABLE_KEY', 'pk_test_'),
                         ('STRIPE_WEBHOOK_SECRET', 'whsec_')):
        value = values[name]
        if not value.startswith(prefix) or len(value) < len(prefix) + 12:
            raise ValueError('Checkout is not configured with test credentials')
    if len(values['FOUNDRY_DOWNLOAD_SECRET']) < 32 or re.match(r'^(replace|change|<)', values['FOUNDRY_DOWNLOAD_SECRET'], re.I):
        raise ValueError('Checkout download signing is not configured')
    for value in values.values():
        if any(word in value.lower() for word in ('replace_me', 'changeme', 'your_secret', 'placeholder')):
            raise ValueError('Checkout configuration contains placeholders')
    for name in ('STRIPE_SUCCESS_URL', 'STRIPE_CANCEL_URL'):
        parsed = urlparse(values[name])
        if (not parsed.hostname or parsed.username or parsed.password or
                not (parsed.scheme == 'https' or parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1', '::1'))):
            raise ValueError('Checkout return URLs must use HTTPS')
    return values


def _dataset(db, id):
    if not isinstance(id, str) or not IDENTIFIER.fullmatch(id):
        return None, response(400, error='invalid_dataset')
    if not db.conn.execute('SELECT 1 FROM datasets WHERE id=?', (id,)).fetchone():
        return None, response(404, error='dataset_not_found')
    try:
        return dataset_detail(db, id, require_saleable=True), None
    except ValueError:
        return None, response(400, error='dataset_unavailable')


def _fingerprint(*values):
    return hashlib.sha256(json.dumps(values, separators=(',', ':')).encode()).hexdigest()


def _checkout(db, payload, settings, auth):
    detail, error = _dataset(db, payload.get('dataset_id'))
    if error:
        return error
    email = payload.get('email')
    if not isinstance(email, str) or len(email) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        return response(400, error='invalid_email')
    amount, currency = detail['price_cents'], detail['currency']
    if type(amount) is not int or amount <= 0 or not isinstance(currency, str) or not re.fullmatch('[A-Za-z]{3}', currency):
        return response(400, error='invalid_price_or_currency')
    currency = currency.upper()
    idem = payload.get('idempotency_key')
    if idem is not None and (not isinstance(idem, str) or not 1 <= len(idem) <= 200):
        return response(400, error='invalid_idempotency_key')
    fingerprint = _fingerprint(detail['id'], email, amount, currency, detail['manifest_sha256'])
    with db.conn:
        db.conn.execute('BEGIN IMMEDIATE')
        old = db.conn.execute('SELECT * FROM orders WHERE buyer_key_id=? AND idempotency_key=?', (auth['key_id'], idem)).fetchone() if idem else None
        if old and old['fingerprint'] != fingerprint:
            return response(409, error='idempotency_conflict')
        if old and old['status'] != 'pending':
            return response(409, error='order_already_processed', order_id=old['id'])
        order_id = old['id'] if old else uuid.uuid4().hex
        if not old:
            db.conn.execute('INSERT INTO orders(id,dataset_id,buyer_email,amount,currency,status,buyer_key_id,idempotency_key,fingerprint,manifest_sha256,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                            (order_id, detail['id'], email, amount, currency, 'pending', auth['key_id'], idem, fingerprint, detail['manifest_sha256'], int(time.time())))
    urls = {}
    for name in ('SUCCESS', 'CANCEL'):
        urls[name.lower() + '_url'] = settings['STRIPE_' + name + '_URL'].replace('{ORDER_ID}', order_id).replace('{DATASET_ID}', detail['id'])
    try:
        session = stripe.StripeClient(settings['STRIPE_SECRET_KEY'], http_client=stripe.RequestsClient(timeout=20), max_network_retries=0).v1.checkout.sessions.create(
            params={'mode': 'payment', 'payment_method_types': ['card'], 'customer_email': email,
                    'adaptive_pricing': {'enabled': False}, 'automatic_tax': {'enabled': False}, 'allow_promotion_codes': False,
                    'client_reference_id': order_id, 'metadata': {'order_id': order_id, 'dataset_id': detail['id']},
                    'line_items': [{'price_data': {'currency': currency.lower(), 'unit_amount': amount,
                        'product_data': {'name': detail['name'][:200]}}, 'quantity': 1}], **urls},
            options={'idempotency_key': 'foundry-order-' + order_id})
        if not isinstance(session, dict):
            session = session.to_dict()
        if session.get('livemode') is not False or not isinstance(session.get('id'), str) or not session['id'].startswith('cs_test_'):
            raise ValueError('Unexpected session mode')
        if old and old['stripe_session_id'] and old['stripe_session_id'] != session['id']:
            raise ValueError('Session binding changed')
        metadata = session.get('metadata')
        if metadata is not None and (not isinstance(metadata, dict) or metadata.get('order_id') != order_id or metadata.get('dataset_id') != detail['id']):
            raise ValueError('Session metadata mismatch')
        parsed = urlparse(session.get('url', ''))
        if parsed.scheme != 'https' or parsed.hostname != 'checkout.stripe.com' or parsed.username or parsed.password:
            raise ValueError('Unexpected checkout URL')
        with db.conn:
            db.conn.execute('UPDATE orders SET stripe_session_id=? WHERE id=? AND status=\'pending\'', (session['id'], order_id))
        return response(200, session_id=session['id'], url=session['url'], order_id=order_id)
    except stripe.InvalidRequestError:
        return response(400, error='invalid_checkout_data', message='Stripe rejected the test price, currency or checkout data')
    except Exception:
        logging.warning('Stripe checkout session creation failed')
        return response(502, error='checkout_failed', message='Unable to create test checkout; retry with the same idempotency key')


def _matches(db, order, session):
    metadata = session.get('metadata') or {}
    if not isinstance(metadata, dict):
        return False
    detail, error = _dataset(db, order['dataset_id'])
    return (not error and detail['manifest_sha256'] == order['manifest_sha256'] and
            session.get('livemode') is False and session.get('mode') == 'payment' and
            session.get('amount_total') == order['amount'] and
            str(session.get('currency', '')).upper() == order['currency'] and
            metadata.get('dataset_id') == order['dataset_id'] and metadata.get('order_id') == order['id'])


def _webhook(db, payload, settings):
    try:
        if not payload.get('signature'):
            raise ValueError('Missing signature')
        timestamp = next(int(part[2:]) for part in payload['signature'].split(',') if part.startswith('t='))
        if abs(time.time() - timestamp) > 300:
            raise ValueError('Webhook timestamp outside tolerance')
        body = base64.b64decode(payload.get('raw_body', ''), validate=True)
        stripe.Webhook.construct_event(body, payload['signature'], settings['STRIPE_WEBHOOK_SECRET'], tolerance=300)
        event = json.loads(body)
        if event.get('livemode') is not False or not isinstance(event.get('data', {}).get('object'), dict):
            raise ValueError('Invalid event')
    except Exception:
        return response(400, error='invalid_webhook_signature_or_body')
    kind = event.get('type')
    session = event['data']['object']
    if (not isinstance(session.get('id'), str) or
            not isinstance(session.get('metadata', {}), dict) or
            not isinstance(session.get('currency', ''), str) or
            type(session.get('amount_total', 0)) is not int):
        return response(400, error='invalid_webhook_body')
    if kind not in ('checkout.session.completed', 'checkout.session.expired', 'checkout.session.async_payment_failed'):
        return response(200, received=True)
    order = db.conn.execute('SELECT * FROM orders WHERE stripe_session_id=?', (session.get('id'),)).fetchone()
    if not order:
        return response(200, received=True)
    matches = _matches(db, order, session)
    with db.conn:
        db.conn.execute('BEGIN IMMEDIATE')
        order = db.conn.execute('SELECT * FROM orders WHERE id=?', (order['id'],)).fetchone()
        if not matches:
            logging.warning('Stripe order mismatch; access withheld')
            db.conn.execute("UPDATE orders SET status='review' WHERE id=?", (order['id'],))
            db.conn.execute('DELETE FROM download_grants WHERE order_id=?', (order['id'],))
        elif kind == 'checkout.session.completed' and session.get('payment_status') == 'paid':
            if order['status'] in ('pending', 'paid'):
                payment = session.get('payment_intent')
                payment = payment if isinstance(payment, str) and payment.startswith('pi_') else None
                db.conn.execute("UPDATE orders SET status='paid',stripe_payment_id=? WHERE id=?", (payment, order['id']))
                db.conn.execute('INSERT OR IGNORE INTO download_grants VALUES(?,?,?)', (order['id'], secrets.token_urlsafe(32), int(time.time()) + TTL))
        elif order['status'] == 'pending' and kind != 'checkout.session.completed':
            db.conn.execute('UPDATE orders SET status=? WHERE id=?', ('expired' if kind.endswith('expired') else 'failed', order['id']))
    return response(200, received=True)


def _sign(order, grant, secret):
    body = base64.urlsafe_b64encode(json.dumps({'order': order['id'], 'dataset': order['dataset_id'], 'nonce': grant['nonce'], 'exp': grant['expires_at']}, separators=(',', ':')).encode()).decode().rstrip('=')
    return body + '.' + hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()


def _order(db, payload, settings, auth):
    if not isinstance(payload.get('id'), str) or not IDENTIFIER.fullmatch(payload['id']):
        return response(404, error='order_not_found')
    row = db.conn.execute('SELECT * FROM orders WHERE id=? AND buyer_key_id=?', (payload.get('id'), auth['key_id'])).fetchone()
    if not row:
        return response(404, error='order_not_found')
    body = {'order_id': row['id'], 'dataset_id': row['dataset_id'], 'status': row['status']}
    grant = db.conn.execute('SELECT * FROM download_grants WHERE order_id=?', (row['id'],)).fetchone()
    if row['status'] == 'paid' and grant:
        body.update(download_url='/api/v1/downloads?token=' + _sign(row, grant, settings['FOUNDRY_DOWNLOAD_SECRET']), expires_at=grant['expires_at'])
    return response(200, **body)


def _download(db, root, payload, settings):
    try:
        token = payload.get('token', '')
        if not isinstance(token, str) or len(token) > 2048:
            raise ValueError('Token')
        body, signature = token.split('.')
        expected = hmac.new(settings['FOUNDRY_DOWNLOAD_SECRET'].encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError('Signature')
        data = json.loads(base64.urlsafe_b64decode(body + '=' * (-len(body) % 4)))
        order = db.conn.execute('SELECT * FROM orders WHERE id=?', (data['order'],)).fetchone()
        grant = db.conn.execute('SELECT * FROM download_grants WHERE order_id=?', (data['order'],)).fetchone()
        if not order or not grant or order['status'] != 'paid' or data['dataset'] != order['dataset_id'] or data['nonce'] != grant['nonce'] or data['exp'] != grant['expires_at']:
            raise ValueError('Grant')
        if int(time.time()) >= grant['expires_at']:
            return response(410, error='download_expired')
        detail, error = _dataset(db, order['dataset_id'])
        if error or detail['manifest_sha256'] != order['manifest_sha256']:
            raise ValueError('Dataset')
        directory = Path(db.conn.execute('SELECT manifest_path FROM datasets WHERE id=?', (order['dataset_id'],)).fetchone()[0]).resolve().parent
        directory.relative_to((root / 'packages').resolve())
        if directory.name != order['dataset_id']:
            raise ValueError('Dataset directory')
        kind = payload.get('kind', 'images')
        for name in ('manifest.csv', 'dataset.json'):
            file = directory / name
            file.resolve().relative_to(directory)
            if file.is_symlink() or not file.is_file():
                raise ValueError('Unsafe package metadata')
        if kind == 'manifest':
            return response(200, path=str(directory / 'manifest.csv'), mime='text/csv', filename='manifest.csv')
        if kind != 'images':
            raise ValueError('Kind')
        destination = root / 'web' / 'downloads'
        destination.mkdir(parents=True, exist_ok=True)
        path = destination / (order['id'] + '.zip')
        # Rebuild to avoid stale archives after files change; never follow symlinks out.
        temporary = destination / (uuid.uuid4().hex + '.tmp')
        try:
            with (directory / 'manifest.csv').open(newline='', encoding='utf-8') as stream:
                rows = list(csv.DictReader(stream))
                ids = [row['id'] for row in rows]
            if any(not IDENTIFIER.fullmatch(id) for id in ids):
                raise ValueError('Image identifier')
            files = [directory / 'manifest.csv', directory / 'dataset.json'] + [directory / 'images' / id for id in ids]
            with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
                for file in files:
                    relative = file.relative_to(directory)
                    file.resolve().relative_to(directory)
                    if file.is_symlink():
                        raise ValueError('Unsafe package')
                    if relative.parts[0] == 'images':
                        row = rows[ids.index(file.name)]
                        provenance = {key: value for key, value in row.items() if key != 'provenance_hash'}
                        provenance['clip_score'] = float(row['clip_score']) if row['clip_score'] else None
                        provenance['frame_ts_ms'] = int(row['frame_ts_ms']) if row['frame_ts_ms'] else None
                        provenance['sha256'] = hashlib.sha256(file.read_bytes()).hexdigest()
                        digest = hashlib.sha256(json.dumps(provenance, sort_keys=True).encode()).hexdigest()
                        if not hmac.compare_digest(digest, row['provenance_hash']):
                            raise ValueError('Image provenance mismatch')
                    archive.write(file, str(relative))
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        return response(200, path=str(path), mime='application/zip', filename=order['dataset_id'] + '.zip')
    except (ValueError, KeyError, TypeError, OSError):
        return response(403, error='invalid_download_grant')


def handle(db, root: Path, payload: dict):
    """Internal JSON adapter; checkout/order retain existing buyer-key semantics."""
    operation = payload.get('op')
    auth = None
    if operation in ('checkout', 'order'):
        auth = authorize(db, payload.get('token') if isinstance(payload.get('token'), str) else None)
        if auth['status'] != 200:
            return auth
    try:
        settings = config()
    except ValueError as error:
        if operation == 'download':
            return response(403, error='invalid_download_grant')
        return response(501, error='checkout_not_implemented', message=str(error))
    if operation == 'checkout':
        return _checkout(db, payload, settings, auth)
    if operation == 'webhook':
        return _webhook(db, payload, settings)
    if operation == 'order':
        return _order(db, payload, settings, auth)
    if operation == 'download':
        return _download(db, Path(root), payload, settings)
    return response(400, error='invalid_payment_operation')

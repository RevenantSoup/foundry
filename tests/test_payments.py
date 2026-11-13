import base64
import hashlib
import hmac
import json
import secrets
import time
from types import SimpleNamespace
import pytest
from foundry.buyers import create_key
from foundry.marketplace import set_price
from foundry.payments import handle
from tests.test_marketplace import listed

@pytest.fixture
def payment(listed, monkeypatch):
    db, path = listed
    set_price(db, path.name, 1999)
    _, key = create_key(db, 'checkout buyer')
    for name, prefix in [('STRIPE_SECRET_KEY','sk_test_'), ('STRIPE_PUBLISHABLE_KEY','pk_test_'), ('STRIPE_WEBHOOK_SECRET','whsec_')]:
        monkeypatch.setenv(name, prefix + secrets.token_hex(24))
    monkeypatch.setenv('FOUNDRY_DOWNLOAD_SECRET', secrets.token_hex(32))
    monkeypatch.setenv('STRIPE_SUCCESS_URL', 'https://example.com/marketplace?order={ORDER_ID}&session={CHECKOUT_SESSION_ID}')
    monkeypatch.setenv('STRIPE_CANCEL_URL', 'https://example.com/marketplace')
    calls = []
    session_id = 'cs_test_' + secrets.token_hex(16)
    def create(params, options):
        calls.append((params,options))
        import stripe
        return stripe.checkout.Session.construct_from({'id':session_id,'livemode':False,'url':'https://checkout.stripe.com/c/pay/test','metadata':params['metadata']}, None)
    monkeypatch.setattr('foundry.payments.stripe.StripeClient', lambda key, **kwargs: SimpleNamespace(v1=SimpleNamespace(checkout=SimpleNamespace(sessions=SimpleNamespace(create=create)))))
    payload = {'op':'checkout','token':key,'dataset_id':path.name,'email':'buyer@example.com','idempotency_key':'one-purchase'}
    return db,path,key,payload,calls

def checkout(payment):
    db,path,key,payload,calls = payment
    result = handle(db,path.parent.parent,payload)
    assert result['status']==200, result
    return result['body']

def event(payment, order, **changes):
    db,path,key,payload,calls = payment
    session = {'id':order['session_id'],'mode':'payment','payment_status':'paid','livemode':False,'amount_total':1999,'currency':'usd',
        'metadata':{'dataset_id':path.name,'order_id':order['order_id']},'payment_intent':'pi_'+secrets.token_hex(8)}
    session.update(changes)
    raw=json.dumps({'id':'evt_'+secrets.token_hex(8),'type':'checkout.session.completed','livemode':False,'data':{'object':session}}).encode()
    return signed(raw)

def signed(raw):
    import os
    stamp=str(int(time.time()))
    signature=hmac.new(os.environ['STRIPE_WEBHOOK_SECRET'].encode(),stamp.encode()+b'.'+raw,hashlib.sha256).hexdigest()
    return {'op':'webhook','raw_body':base64.b64encode(raw).decode(),'signature':f't={stamp},v1={signature}'}

def test_pending_order_once_and_exact_values(payment):
    db,path,key,payload,calls=payment
    first=checkout(payment);second=checkout(payment)
    assert first==second
    row=db.conn.execute('select * from orders').fetchone()
    assert db.conn.execute('select count(*) from orders').fetchone()[0]==1
    assert (row['dataset_id'],row['buyer_email'],row['amount'],row['currency'],row['status'])==(path.name,'buyer@example.com',1999,'USD','pending')
    assert calls[0][0]['line_items'][0]['price_data']['unit_amount']==1999
    assert calls[0][1]==calls[1][1]
    assert calls[0][0]['metadata']['order_id']==row['id']
    assert not any(word in row.keys() for word in ('card','cvc','expiry'))
    payload['email']='different@example.com'
    assert handle(db,path.parent.parent,payload)['status']==409

def test_valid_webhook_paid_idempotent_grant_and_download(payment):
    db,path,key,payload,calls=payment;order=checkout(payment);root=path.parent.parent
    assert handle(db,root,event(payment,order))['status']==200
    grant=dict(db.conn.execute('select * from download_grants').fetchone())
    assert handle(db,root,event(payment,order))['status']==200
    assert dict(db.conn.execute('select * from download_grants').fetchone())==grant
    assert db.conn.execute('select count(*) from orders').fetchone()[0]==1
    result=handle(db,root,{'op':'order','id':order['order_id'],'token':key})
    token=result['body']['download_url'].split('token=')[1]
    download=handle(db,root,{'op':'download','token':token})
    assert download['status']==200
    import zipfile
    with zipfile.ZipFile(download['body']['path']) as archive:
        assert {'manifest.csv','dataset.json'} <= set(archive.namelist())
        assert len([n for n in archive.namelist() if n.startswith('images/')])==200
    assert handle(db,root,{'op':'download','token':token,'kind':'manifest'})['status']==200
    assert handle(db,root,{'op':'download','token':token+'tampered'})['status']==403
    with db.conn:db.conn.execute("update orders set status='pending'")
    assert handle(db,root,{'op':'download','token':token})['status']==403
    with db.conn:db.conn.execute("update orders set status='paid'")
    monkey_time=grant['expires_at']+1
    from unittest.mock import patch
    with patch('foundry.payments.time.time',return_value=monkey_time):
        assert handle(db,root,{'op':'download','token':token})['status']==410

@pytest.mark.parametrize('variant',['missing','invalid','tampered','wrong_json','wrong_shape'])
def test_invalid_webhook_grants_nothing(payment,variant):
    db,path,*_=payment;order=checkout(payment);payload=event(payment,order)
    if variant=='missing':payload.pop('signature')
    elif variant=='invalid':payload['signature']='invalid'
    elif variant=='tampered':payload['raw_body']=base64.b64encode(b'{}').decode()
    elif variant=='wrong_json':payload=signed(b'not json')
    else:payload=signed(b'[]')
    assert handle(db,path.parent.parent,payload)['status']==400
    assert db.conn.execute('select count(*) from download_grants').fetchone()[0]==0
    assert db.conn.execute('select status from orders').fetchone()[0]=='pending'

@pytest.mark.parametrize('change',[{'amount_total':1},{'currency':'eur'},{'metadata':{'dataset_id':'other'}},{'livemode':True}])
def test_mismatch_no_grant(payment,change):
    db,path,*_=payment;order=checkout(payment)
    assert handle(db,path.parent.parent,event(payment,order,**change))['status']==200
    assert db.conn.execute('select status from orders').fetchone()[0]=='review'
    assert db.conn.execute('select count(*) from download_grants').fetchone()[0]==0
    handle(db,path.parent.parent,event(payment,order))
    assert db.conn.execute('select count(*) from download_grants').fetchone()[0]==0

def test_checkout_validation_and_unconfigured(payment,monkeypatch):
    db,path,key,payload,calls=payment;root=path.parent.parent
    assert handle(db,root,{**payload,'dataset_id':'missing'})['status']==404
    assert handle(db,root,{**payload,'dataset_id':'../bad'})['status']==400
    assert handle(db,root,{**payload,'email':'invalid'})['status']==400
    set_price(db,path.name,0)
    assert handle(db,root,payload)['status']==400
    monkeypatch.delenv('STRIPE_WEBHOOK_SECRET')
    assert handle(db,root,payload)['status']==501
    assert handle(db,root,{'op':'webhook'})['status']==501
    assert handle(db,root,{**payload,'token':'bad'})['status']==401

def test_unknown_grant_and_foreign_owner(payment):
    db,path,key,payload,calls=payment;order=checkout(payment);root=path.parent.parent
    assert handle(db,root,{'op':'download','token':'unknown'})['status']==403
    _,other=create_key(db,'other')
    assert handle(db,root,{'op':'order','token':other,'id':order['order_id']})['status']==404
    assert 'download_url' not in handle(db,root,{'op':'order','token':key,'id':order['order_id']})['body']


def test_expired_failed_sessions_never_resurrect(payment):
    db,path,key,payload,calls=payment;order=checkout(payment);root=path.parent.parent
    original=event(payment,order)
    raw=json.loads(base64.b64decode(original['raw_body']))
    raw['type']='checkout.session.expired'
    assert handle(db,root,signed(json.dumps(raw).encode()))['status']==200
    assert db.conn.execute('select status from orders').fetchone()[0]=='expired'
    handle(db,root,event(payment,order))
    assert db.conn.execute('select count(*) from download_grants').fetchone()[0]==0


def test_unpaid_completed_and_tampered_package_no_access(payment):
    db,path,key,payload,calls=payment;order=checkout(payment);root=path.parent.parent
    handle(db,root,event(payment,order,payment_status='unpaid'))
    assert db.conn.execute('select count(*) from download_grants').fetchone()[0]==0
    handle(db,root,event(payment,order))
    token=handle(db,root,{'op':'order','id':order['order_id'],'token':key})['body']['download_url'].split('token=')[1]
    (path/'manifest.csv').write_text('tampered')
    assert handle(db,root,{'op':'download','token':token})['status']==403


def test_invalid_configuration_and_price(payment,monkeypatch):
    db,path,key,payload,calls=payment;root=path.parent.parent
    with db.conn:db.conn.execute("update datasets set currency='' where id=?",(path.name,))
    assert handle(db,root,payload)['status']==400
    monkeypatch.setenv('STRIPE_SECRET_KEY','sk_live_'+secrets.token_hex(24))
    assert handle(db,root,payload)['status']==501

@pytest.mark.parametrize('change',[{'metadata':[]},{'id':[]},{'currency':[]},{'amount_total':True}])
def test_signed_malformed_session_rejected(payment,change):
    db,path,*_=payment;order=checkout(payment)
    assert handle(db,path.parent.parent,event(payment,order,**change))['status']==400
    assert db.conn.execute('select count(*) from download_grants').fetchone()[0]==0

def test_future_webhook_rejected(payment):
    import os
    db,path,*_=payment;order=checkout(payment);payload=event(payment,order)
    body=base64.b64decode(payload['raw_body']);stamp=str(int(time.time())+301)
    digest=hmac.new(os.environ['STRIPE_WEBHOOK_SECRET'].encode(),stamp.encode()+b'.'+body,hashlib.sha256).hexdigest()
    payload['signature']=f't={stamp},v1={digest}'
    assert handle(db,path.parent.parent,payload)['status']==400

def test_image_tamper_and_metadata_symlink(payment):
    db,path,key,payload,calls=payment;order=checkout(payment);root=path.parent.parent
    handle(db,root,event(payment,order))
    token=handle(db,root,{'op':'order','id':order['order_id'],'token':key})['body']['download_url'].split('token=')[1]
    next((path/'images').iterdir()).write_bytes(b'tampered image')
    assert handle(db,root,{'op':'download','token':token})['status']==403
    external=root/'external.json';external.write_text('{}')
    (path/'dataset.json').unlink();(path/'dataset.json').symlink_to(external)
    assert handle(db,root,{'op':'download','token':token,'kind':'manifest'})['status']==403


def test_unknown_download_denied_when_checkout_unconfigured(payment,monkeypatch):
    db,path,key,payload,calls=payment
    monkeypatch.delenv('STRIPE_SECRET_KEY')
    assert handle(db,path.parent.parent,{'op':'download','token':'unknown'})['status']==403


def test_stripe_rejected_price_is_bad_request(payment,monkeypatch):
    import stripe
    db,path,key,payload,calls=payment
    def reject(*args,**kwargs):
        raise stripe.InvalidRequestError('unsupported test amount',param='unit_amount')
    monkeypatch.setattr('foundry.payments.stripe.StripeClient',lambda *a,**kw:SimpleNamespace(v1=SimpleNamespace(checkout=SimpleNamespace(sessions=SimpleNamespace(create=reject)))))
    result=handle(db,path.parent.parent,payload)
    assert result['status']==400
    assert db.conn.execute('SELECT count(*) FROM download_grants').fetchone()[0]==0

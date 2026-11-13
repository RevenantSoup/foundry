"""TEST ONLY SDK transport: realistic Stripe resources, never network/card data."""
import hashlib
from types import SimpleNamespace
import stripe

def install():
    def create(params, options):
        identifier='cs_test_'+hashlib.sha256(options['idempotency_key'].encode()).hexdigest()[:32]
        return stripe.checkout.Session.construct_from({'id':identifier,'url':'https://checkout.stripe.com/c/pay/'+identifier,
          'livemode':False,'metadata':params['metadata'],'amount_total':params['line_items'][0]['price_data']['unit_amount'],
          'currency':params['line_items'][0]['price_data']['currency'],'mode':'payment'},None)
    stripe.StripeClient=lambda *_args,**_kwargs:SimpleNamespace(v1=SimpleNamespace(checkout=SimpleNamespace(sessions=SimpleNamespace(create=create))))

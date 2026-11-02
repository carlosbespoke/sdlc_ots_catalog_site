"""Observation driver.

Runs as an unprivileged user. It reads the whole case list from **stdin** before any candidate code
is imported: a JSON list of case sources, in order, with no identifiers (the trusted parent keeps
the identifiers and maps results back by position). It then points its own standard input at
/dev/null and marks itself non-dumpable, so no later process of the same user can read the list
through /proc. Every case runs in its own fresh interpreter (``python -I``, so no PYTHON* variable,
user site or working directory reaches it) whose ``sys.path`` gets the candidate's repository root
(the directory holding ``djstripe``) appended *after* the standard library and site-packages: a
candidate file named like a standard-library or third-party module can never replace one. Each
case is a short Python module that assigns ``result``; its source is passed to the runner on
**stdin**, read before any candidate code is imported, and executed from memory as
``case_module``. The runner also points its standard input at /dev/null and marks itself
non-dumpable before the case starts. The case runs in its own empty working directory (an opaque
temporary name that reveals nothing about the case), and no file, path, argument or environment
variable the candidate can read names or contains the case. Cases run one at a time, and before each
case starts the driver kills every other process of its own uid (anything an earlier case left
running), so no candidate process is alive while a runner holds an unread case on its stdin. The driver records the
JSON-normalised ``result`` of each case, or the name of the exception class when a case raises,
and writes the list of observations to ``argv[1]``. It never sees an expected value: the trusted
parent holds those and compares.

    python driver.py RESULT_PATH CANDIDATE_TREE < case-sources.json
"""
import ctypes
import json
import os
import signal
import subprocess
import sys
import tempfile


def seal_self():
    """Detach stdin and make this process non-dumpable (no /proc/<pid>/{fd,mem,environ} for peers)."""
    null = os.open(os.devnull, os.O_RDONLY)
    os.dup2(null, 0)
    os.close(null)
    try:
        ctypes.CDLL(None, use_errno=True).prctl(4, 0, 0, 0, 0)  # PR_SET_DUMPABLE, 0
    except (OSError, AttributeError):
        pass


def live_peers(me, uid):
    """Other live (non-zombie) processes of this uid."""
    peers = []
    for pid in os.listdir("/proc"):
        if not pid.isdigit() or int(pid) == me:
            continue
        try:
            with open("/proc/%s/status" % pid) as handle:
                fields = dict(line.split(":", 1) for line in handle if ":" in line)
        except (OSError, ValueError):
            continue
        if int(fields.get("Uid", "-1").split()[0]) == uid and fields.get("State", "").split()[:1] not in (["Z"], ["X"]):
            peers.append(int(pid))
    return peers


def sweep_peers():
    """Kill every other process of this uid before the next case starts (none is legitimate)."""
    me, uid = os.getpid(), os.getuid()
    if uid == 0:
        return  # authoring harnesses run this driver as root; the grader always runs it as nobody
    for _ in range(200):
        try:
            os.kill(-1, signal.SIGKILL)  # every process this uid may signal, except this one
        except ProcessLookupError:
            pass
        if not live_peers(me, uid):
            return
    raise RuntimeError("a previous case left processes that could not be stopped")


RUNNER = r'''
import ctypes, json, os, sys, types, warnings
case_dir = os.getcwd()
tree = os.environ.pop("CASE_TREE")
# The case source arrives on stdin and is consumed before any candidate code runs.
case_source = sys.stdin.read()
null = os.open(os.devnull, os.O_RDONLY)
os.dup2(null, 0)
os.close(null)
sys.stdin = open(os.devnull)
try:
    ctypes.CDLL(None, use_errno=True).prctl(4, 0, 0, 0, 0)
except (OSError, AttributeError):
    pass
# Third-party modules first, from site-packages, before the candidate tree is reachable.
import django, django.conf, django.test, django.core.management, asgiref, sqlparse, stripe  # noqa: E401,F401
sys.path.append(tree)
warnings.simplefilter("ignore")


def norm(value, depth=0):
    if depth > 14:
        return repr(value)[:500]
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value[:2000]
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, bytes):
        return {"bytes": value.decode("latin-1")[:2000]}
    if isinstance(value, dict):
        return {str(k): norm(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return {"set": sorted((norm(v, depth + 1) for v in value), key=repr)}
    if isinstance(value, (list, tuple)):
        return [norm(v, depth + 1) for v in value]
    return {"repr": repr(value)[:500]}


try:
    case_module = types.ModuleType("case_module")
    sys.modules["case_module"] = case_module
    exec(compile(case_source, "<case>", "exec"), case_module.__dict__)
    out = {"value": norm(case_module.result)}
except BaseException as exception:  # noqa: BLE001
    out = {"error": type(exception).__name__[:100]}
sys.stdout.flush()
with open(os.path.join(case_dir, "result.json"), "w") as handle:
    json.dump(out, handle)
os._exit(0)
'''

PREAMBLE = r'''# Observation preamble of dj-stripe-pdk-ots: the colleague original's tests/private/replay_driver.py
# without its main block (it configured a throwaway Django project with an in-memory SQLite database,
# created the djstripe tables and replayed calls through `observe`). Every case runs in its own fresh
# interpreter, so this setup runs once per case. `replay` is `observe` under the name the case code uses.
import hashlib
import hmac
import json
import sys
import warnings

from django.conf import settings
# Coverage sweep: the original's settings plus the admin, sessions and messages apps, middleware and
# templates, and the sandbox URLs (admin + dj-stripe under /stripe/), so admin and view behaviour can be
# observed too. compare_original.py proves the 37 replayed calls still equal the original's values.
settings.configure(SECRET_KEY='replay', INSTALLED_APPS=['django.contrib.admin','django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','djstripe'], DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':':memory:'}}, USE_TZ=True, DJSTRIPE_FOREIGN_KEY_TO_FIELD='id', STRIPE_SECRET_KEY='sk_test_replay', ROOT_URLCONF='djsproject.urls', DEFAULT_AUTO_FIELD='django.db.models.BigAutoField', MIGRATION_MODULES={'admin':None,'auth':None,'contenttypes':None,'sessions':None,'messages':None,'djstripe':None}, ALLOWED_HOSTS=['testserver'], MIDDLEWARE=['django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','django.contrib.messages.middleware.MessageMiddleware'], TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}])
import django
django.setup()
from django.core.management import call_command
from django.test import RequestFactory, override_settings
from djstripe.models import Account, Event, WebhookEndpoint, WebhookEventTrigger
from djstripe.event_handlers import djstripe_receiver
from djstripe import signals
call_command('migrate', run_syncdb=True, verbosity=0)


def payload(event_type='balance.available'):
    return {'id':'evt_replay','object':'event','account':'acct_replay','livemode':False,'api_version':'2020-08-27','created':1600000000,'pending_webhooks':1,'request':None,'type':event_type,'data':{'object':{'id':'obj_replay','object':'balance'}}}


def observe(c):
    """Observe real model, signal and transaction behavior via public APIs."""
    call_command('flush', verbosity=0, interactive=False)
    Account.objects.create(id='acct_replay', livemode=False, stripe_data={})
    endpoint=WebhookEndpoint.objects.create(id='we_replay', livemode=False, secret='whsec_endpoint', enabled_events=['*'], djstripe_validation_method='none', djstripe_tolerance=0, stripe_data={})
    if c['op']=='validation':
        data=payload()
        for key in c.get('omit',[]): data.pop(key,None)
        if c.get('invalid_json'): body='not json'
        else: body=json.dumps(data,sort_keys=True)
        endpoint.djstripe_validation_method=c.get('method','none')
        # Zero tolerance disables age checking through the SDK's supported API.
        secret=c.get('signed_with','whsec_endpoint')
        digest=hmac.new(secret.encode(),('1600000000.'+body).encode(),hashlib.sha256).hexdigest()
        headers={c.get('header_name','stripe-signature'): 't=1600000000,v1='+digest}
        if 'forward' in c: headers['X-Djstripe-Webhook-Secret']=c['forward']
        obj=WebhookEventTrigger(body=body,headers=headers,webhook_endpoint=endpoint)
        with override_settings(DEBUG=c.get('debug',False)):
            return {'valid':obj.validate(api_key='sk_test_replay',secret=endpoint.secret)}
    received=[]
    lifecycle=[]
    connections=[]
    registrations=c.get('registrations','balance.available')
    if c.get('tuple'): registrations=tuple(registrations)
    def receiver(sender,event,**kwargs):
        received.append({'sender':sender is Event,'saved':Event.objects.filter(pk=event.pk).exists(),'type':event.type})
        Account.objects.create(id='acct_effect_'+str(len(received)),livemode=False,stripe_data={})
        if c.get('failure')=='event': raise ValueError('receiver failed')
    djstripe_receiver(registrations)(receiver)
    names=registrations if isinstance(registrations,(list,tuple)) else [registrations]
    connections += [(signals.WEBHOOK_SIGNALS[n],receiver,Event) for n in names]
    for name in ['webhook_pre_validate','webhook_post_validate','webhook_pre_process','webhook_post_process','webhook_processing_error']:
        def hook(sender,instance,_name=name,**kwargs):
            item={'name':_name,'sender':sender is WebhookEventTrigger,'instance':isinstance(instance,WebhookEventTrigger)}
            if 'valid' in kwargs: item['valid']=kwargs['valid']
            if 'api_key' in kwargs: item['api_key']=kwargs['api_key']
            if 'exception' in kwargs: item['exception']=type(kwargs['exception']).__name__;item['data']=kwargs['data']
            lifecycle.append(item)
            if _name=='webhook_pre_process':
                Account.objects.get_or_create(id='acct_lifecycle',defaults={'livemode':False,'stripe_data':{}})
                if c.get('failure')=='pre': raise ValueError('lifecycle failed')
        signal=getattr(signals,name);signal.connect(hook,sender=WebhookEventTrigger,weak=False)
        connections.append((signal,hook,WebhookEventTrigger))
    results=[]
    try:
        for i,event_type in enumerate(c.get('types',['balance.available'])):
            data=payload(event_type)
            if not c.get('duplicate'): data['id']+='_'+str(i)
            if c.get('missing'): data.pop('livemode')
            try:
                if c['op']=='delivery':
                    request=RequestFactory().post('/',data=json.dumps(data),content_type='application/json',HTTP_STRIPE_SIGNATURE='unused')
                    obj=WebhookEventTrigger.from_request(request,webhook_endpoint=endpoint)
                    results.append({'valid':obj.valid,'processed':obj.processed})
                else:
                    obj=Event.process(data)
                    results.append({'id':obj.id,'type':obj.type})
            except ValueError:
                results.append({'error':'ValueError'})
            if c.get('retry') and i==0: c=dict(c,failure=None)
        triggers=[{'valid':t.valid,'processed':t.processed,'error':bool(t.exception),'traceback':bool(t.traceback),'event':t.event_id is not None} for t in WebhookEventTrigger.objects.order_by('pk')]
        return {'results':results,'received':received,'lifecycle':lifecycle,'events':list(Event.objects.order_by('id').values_list('id',flat=True)), 'effects':list(Account.objects.filter(id__startswith='acct_effect_').order_by('id').values_list('id',flat=True)), 'lifecycle_write':Account.objects.filter(id='acct_lifecycle').exists(), 'triggers':triggers}
    finally:
        for signal,handler,sender in connections: signal.disconnect(handler,sender=sender)


replay = observe


# ---------------------------------------------------------------------------------------------------
# Coverage-sweep helpers (dj-stripe-pdk-ots). Everything above is the original replay driver, unchanged.
# The environment has no network: FakeStripe stands in for the Stripe API at the stripe SDK's HTTP
# client layer, records every request the code under test makes (method, path, form parameters, API key,
# Stripe-Version and Stripe-Account headers) and answers from per-case routes.
# ---------------------------------------------------------------------------------------------------
import copy
import datetime
import urllib.parse
from decimal import Decimal

import stripe
from stripe._http_client import HTTPClient
from django.test import Client


class FakeStripe(HTTPClient):
    name = "fake"

    def __init__(self, routes=None):
        super().__init__()
        self.routes = dict(routes or {})
        self.requests = []

    def request(self, method, url, headers, post_data=None, *, _usage=None):
        parts = urllib.parse.urlsplit(url)
        body = post_data.decode() if isinstance(post_data, bytes) else (post_data or "")
        params = dict(urllib.parse.parse_qsl(parts.query, keep_blank_values=True))
        params.update(urllib.parse.parse_qsl(body, keep_blank_values=True))
        headers = dict(headers or {})
        entry = {"method": method.upper(), "path": parts.path, "params": params,
                 "api_key": headers.get("Authorization", "").replace("Bearer ", ""),
                 "stripe_version": headers.get("Stripe-Version"),
                 "stripe_account": headers.get("Stripe-Account")}
        self.requests.append(entry)
        handler = self.routes.get((entry["method"], parts.path))
        if handler is None:
            for (route_method, route_path), candidate in self.routes.items():
                if route_method == entry["method"] and route_path.endswith("*") \
                        and parts.path.startswith(route_path[:-1]):
                    handler = candidate
                    break
        if handler is None:
            return json.dumps({"error": {"type": "invalid_request_error",
                                         "message": "No such resource"}}), 404, {}
        result = handler(entry) if callable(handler) else copy.deepcopy(handler)
        status = 200
        if isinstance(result, tuple):
            result, status = result
        return json.dumps(result), status, {}

    def request_stream(self, method, url, headers, post_data=None, *, _usage=None):
        raise NotImplementedError

    def calls(self, method=None, prefix=""):
        return [(r["method"], r["path"]) for r in self.requests
                if (method is None or r["method"] == method) and r["path"].startswith(prefix)]


COV_KEY = "sk_test_" + "C0v3r4g3" * 3  # a well-formed test secret key (the replay's placeholder is not)


def fake_stripe(routes=None, key=COV_KEY):
    """Install the offline Stripe stub. Unless the case routes it, GET /v1/account answers with the platform
    account `acct_platform`; the settings' default secret key becomes `key`."""
    routes = dict(routes or {})
    routes.setdefault(("GET", "/v1/account"), lambda entry: account_data("acct_platform"))
    routes.setdefault(("GET", "/v1/accounts/*"), lambda entry: account_data(entry["path"].rsplit("/", 1)[-1]))
    fake = FakeStripe(routes)
    stripe.default_http_client = fake
    if key is not None:
        settings.STRIPE_SECRET_KEY = key
    return fake


def stripe_list(path, *objects):
    return {"object": "list", "data": [copy.deepcopy(o) for o in objects], "has_more": False, "url": path}


def product_data(id="prod_cov", name="Premium plan", **extra):
    data = {"id": id, "object": "product", "active": True, "created": 1600000000, "livemode": False,
            "metadata": {}, "name": name, "description": None, "images": [], "type": "service",
            "updated": 1600000000, "url": None, "statement_descriptor": None, "unit_label": None,
            "default_price": None, "marketing_features": [], "package_dimensions": None,
            "shippable": None, "tax_code": None}
    data.update(extra)
    return data


def customer_data(id="cus_cov", email="cov@example.com", **extra):
    data = {"id": id, "object": "customer", "address": None, "balance": 0, "created": 1600000000,
            "currency": "usd", "default_source": None, "delinquent": False, "description": None,
            "discount": None, "email": email, "invoice_prefix": "COV0001",
            "invoice_settings": {"custom_fields": None, "default_payment_method": None, "footer": None,
                                 "rendering_options": None},
            "livemode": False, "metadata": {}, "name": None, "next_invoice_sequence": 1, "phone": None,
            "preferred_locales": [], "shipping": None, "tax_exempt": "none", "test_clock": None}
    data.update(extra)
    return data


def account_data(id="acct_cov", **extra):
    data = {"id": id, "object": "account", "business_profile": {"name": "Cov Shop", "url": "https://shop.example"},
            "business_type": "company", "capabilities": {}, "charges_enabled": True, "country": "US",
            "created": 1600000000, "default_currency": "usd", "details_submitted": True,
            "email": "owner@example.com", "metadata": {}, "payouts_enabled": True,
            "settings": {"dashboard": {"display_name": "Cov Dashboard", "timezone": "Etc/UTC"}},
            "type": "standard", "livemode": False}
    data.update(extra)
    return data


def price_data(id="price_cov", product="prod_cov", unit_amount=1000, recurring=True, **extra):
    data = {"id": id, "object": "price", "active": True, "billing_scheme": "per_unit", "created": 1600000000,
            "currency": "usd", "livemode": False, "lookup_key": None, "metadata": {}, "nickname": None,
            "product": product, "recurring": ({"aggregate_usage": None, "interval": "month", "interval_count": 1,
                                                "usage_type": "licensed", "trial_period_days": None}
                                               if recurring else None),
            "tax_behavior": "unspecified", "tiers_mode": None, "transform_quantity": None,
            "type": "recurring" if recurring else "one_time", "unit_amount": unit_amount,
            "unit_amount_decimal": str(unit_amount)}
    data.update(extra)
    return data


def subscription_data(id="sub_cov", customer="cus_cov", price=None, status="active", start=1600000000,
                      end=1602592000, **extra):
    price = price or price_data()
    data = {"id": id, "object": "subscription", "application_fee_percent": None, "billing_cycle_anchor": start,
            "cancel_at": None, "cancel_at_period_end": False, "canceled_at": None,
            "collection_method": "charge_automatically", "created": start, "currency": "usd",
            "current_period_end": end, "current_period_start": start, "customer": customer,
            "days_until_due": None, "default_payment_method": None, "default_source": None,
            "default_tax_rates": [], "discount": None, "discounts": [], "ended_at": None,
            "items": {"object": "list", "has_more": False, "url": "/v1/subscription_items?subscription=" + id,
                      "data": [{"id": "si_" + id, "object": "subscription_item", "created": start, "metadata": {},
                                "price": price, "quantity": 1, "subscription": id, "tax_rates": [],
                                "current_period_start": start, "current_period_end": end}]},
            "latest_invoice": None, "livemode": False, "metadata": {}, "pause_collection": None,
            "pending_setup_intent": None, "pending_update": None, "plan": None, "quantity": 1,
            "schedule": None, "start_date": start, "status": status, "test_clock": None, "trial_end": None,
            "trial_start": None}
    data.update(extra)
    return data


def charge_data(id="ch_cov", customer="cus_cov", amount=1000, **extra):
    data = {"id": id, "object": "charge", "amount": amount, "amount_captured": amount, "amount_refunded": 0,
            "application_fee": None, "application_fee_amount": None, "balance_transaction": None,
            "billing_details": {}, "captured": True, "created": 1600000000, "currency": "usd",
            "customer": customer, "description": None, "dispute": None, "disputed": False,
            "failure_code": None, "failure_message": None, "fraud_details": {}, "invoice": None,
            "livemode": False, "metadata": {}, "on_behalf_of": None, "outcome": None, "paid": True,
            "payment_intent": None, "payment_method": None, "payment_method_details": None,
            "receipt_email": None, "receipt_number": None, "receipt_url": None, "refunded": False,
            "refunds": {"object": "list", "data": [], "has_more": False, "url": "/v1/charges/" + id + "/refunds"},
            "review": None, "shipping": None, "source": None, "source_transfer": None,
            "statement_descriptor": None, "status": "succeeded", "transfer": None, "transfer_data": None,
            "transfer_group": None}
    data.update(extra)
    return data


def payment_method_data(id="pm_cov", customer="cus_cov", **extra):
    data = {"id": id, "object": "payment_method", "billing_details": {"address": None, "email": None,
            "name": None, "phone": None}, "card": {"brand": "visa", "last4": "4242", "exp_month": 12,
            "exp_year": 2034, "country": "US", "funding": "credit"}, "created": 1600000000,
            "customer": customer, "livemode": False, "metadata": {}, "type": "card"}
    data.update(extra)
    return data


def invoice_data(id="in_cov", customer="cus_cov", status="draft", **extra):
    data = {"id": id, "object": "invoice", "account_country": "US", "account_name": "Cov", "amount_due": 1500,
            "amount_paid": 0, "amount_remaining": 1500, "attempt_count": 0, "attempted": False,
            "auto_advance": True, "billing_reason": "manual", "charge": None,
            "collection_method": "charge_automatically", "created": 1600000000, "currency": "usd",
            "customer": customer, "customer_email": "cov@example.com", "default_payment_method": None,
            "default_source": None, "default_tax_rates": [], "description": None, "discount": None,
            "discounts": [], "due_date": None, "ending_balance": None, "hosted_invoice_url": None,
            "invoice_pdf": None, "lines": {"object": "list", "data": [], "has_more": False,
            "url": "/v1/invoices/" + str(id) + "/lines"}, "livemode": False, "metadata": {},
            "next_payment_attempt": None, "number": None, "paid": status == "paid", "payment_intent": None,
            "period_end": 1600000000, "period_start": 1600000000, "receipt_number": None,
            "starting_balance": 0, "statement_descriptor": None, "status": status, "subscription": None,
            "subtotal": 1500, "tax": None, "total": 1500, "total_tax_amounts": [], "webhooks_delivered_at": None}
    data.update(extra)
    return data


def invoiceitem_data(id="ii_cov", customer="cus_cov", amount=250, **extra):
    data = {"id": id, "object": "invoiceitem", "amount": amount, "currency": "usd", "customer": customer,
            "date": 1600000000, "description": None, "discountable": True, "discounts": [], "invoice": None,
            "livemode": False, "metadata": {}, "period": {"start": 1600000000, "end": 1600000000},
            "price": None, "plan": None, "proration": False, "quantity": 1, "subscription": None,
            "tax_rates": [], "unit_amount": amount, "unit_amount_decimal": str(amount)}
    data.update(extra)
    return data


def form_posts(fake, path_prefix=""):
    return [(r["path"], dict(sorted(r["params"].items()))) for r in fake.requests
            if r["method"] == "POST" and r["path"].startswith(path_prefix)]


def sobj(data, cls=None):
    """`data` as the stripe SDK hands it over (StripeObject with ListObject lists), as sync_from_stripe_data expects."""
    return (cls or stripe.StripeObject).construct_from(copy.deepcopy(data), COV_KEY)


def signed_headers(body, secret, timestamp):
    digest = hmac.new(secret.encode(), (str(timestamp) + "." + body).encode(), hashlib.sha256).hexdigest()
    return "t=%d,v1=%s" % (timestamp, digest)


def endpoint(id="we_cov", method="verify_signature", secret="whsec_cov", tolerance=300, **extra):
    return WebhookEndpoint.objects.create(id=id, livemode=False, secret=secret, enabled_events=["*"],
                                          djstripe_validation_method=method, djstripe_tolerance=tolerance,
                                          stripe_data={}, **extra)


class LogCapture:
    """Collects the messages logged by dj-stripe's loggers during a block."""

    def __enter__(self):
        import logging
        self.records = []
        outer = self

        class Handler(logging.Handler):
            def emit(self, record):
                outer.records.append(record.getMessage())

        self.handler = Handler()
        self.logger = logging.getLogger("djstripe")
        self.logger.addHandler(self.handler)
        self.level = self.logger.level
        self.logger.setLevel(logging.DEBUG)
        return self

    def __exit__(self, *exc):
        self.logger.removeHandler(self.handler)
        self.logger.setLevel(self.level)
        return False


def webhook_endpoint_data(id="we_admin", url="https://example.com/stripe/webhook/x/", **extra):
    data = {"id": id, "object": "webhook_endpoint", "api_version": "2020-08-27", "application": None,
            "created": 1600000000, "description": None, "enabled_events": ["*"], "livemode": False,
            "metadata": {}, "secret": "whsec_admin", "status": "enabled", "url": url}
    data.update(extra)
    return data


def admin_client():
    from django.contrib.auth import get_user_model
    from django.test import Client
    user = get_user_model().objects.create_superuser("root", "root@example.com", "pw")
    client = Client(raise_request_exception=False)
    client.force_login(user)
    return client
'''


def run_case(source, tree, scratch):
    # opaque per-case directory: nothing the candidate can see names the observation
    directory = tempfile.mkdtemp(prefix="case-", dir=scratch)
    environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": directory,
                   "TMPDIR": directory, "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8", "TZ": "UTC",
                   "CASE_TREE": tree}
    try:
        subprocess.run([sys.executable, "-I", "-B", "-c", RUNNER], cwd=directory, env=environment,
                       input=(PREAMBLE + "\n" + source + "\n").encode(), stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=180)
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    try:
        with open(os.path.join(directory, "result.json")) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {"error": "no-result"}


def main():
    sources = json.loads(sys.stdin.read())
    seal_self()
    result_path, tree = sys.argv[1], os.path.abspath(sys.argv[2])
    scratch = tempfile.mkdtemp(prefix="obs-")
    results = []
    for source in sources:
        sweep_peers()
        results.append(run_case(source, tree, scratch))
    sweep_peers()
    with open(result_path, "w") as handle:
        json.dump({"results": results}, handle)


if __name__ == "__main__":
    main()

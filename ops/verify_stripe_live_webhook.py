"""Run explicitly on the production host after deploying the isolated verifier.

Only portal metadata and temporary endpoint event selection are changed in Stripe.
No customer, subscription, invoice or charge is created. Secrets never enter argv.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.parse
import urllib.request

SERVICE = Path('/home/deploy/apps/django-analytics-dashboard')
PRIVATE = Path('/root/.config/nuviamy')
PROBE_EVENT = 'billing_portal.configuration.updated'
MARKER = 'nuviamy_webhook_verification'


def read_env(path):
    values = {}
    for line in path.read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            values[key.strip()] = value.strip().strip('\"\x27')
    return values


def app_snapshot(nonce):
    # Read-only ORM inspection. Only fingerprints and the probe receipt leave Django.
    code = '''
import hashlib,json
from django.conf import settings
from apps.billing.models import PracticeSubscription
from apps.audit.models import AuditLog
rows=list(PracticeSubscription.objects.order_by('pk').values())
proof=list(AuditLog.objects.filter(object_type='stripe_live_webhook_verification',metadata__probe_id=PROBE_NONCE_VALUE).values_list('metadata',flat=True))
print('PROBE_JSON='+json.dumps({'test_mode':settings.STRIPE_SECRET_KEY.startswith(('sk_test_','rk_test_')),'verifier_enabled':bool(settings.STRIPE_LIVE_VERIFY_WEBHOOK_SECRET and settings.STRIPE_LIVE_VERIFY_NONCE==PROBE_NONCE_VALUE),'subscriptions_sha256':hashlib.sha256(json.dumps(rows,default=str,sort_keys=True).encode()).hexdigest(),'receipts':proof}))
'''.replace('PROBE_NONCE_VALUE', repr(nonce))
    result = subprocess.run(['docker', 'compose', 'exec', '-T', 'web', 'python', 'manage.py', 'shell'],
                            cwd=SERVICE, input=code, text=True, capture_output=True, check=True)
    return json.loads(next(line[11:] for line in result.stdout.splitlines() if line.startswith('PROBE_JSON=')))


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-probe', action='store_true', required=True)
    parser.parse_args()
    state_path = PRIVATE / 'webhook-verification-state.json'
    state = json.loads(state_path.read_text())
    candidate = read_env(PRIVATE / 'stripe-live.env')
    active_path = SERVICE / '.env'
    active = read_env(active_path)
    nonce = state['nonce']
    assert active['STRIPE_SECRET_KEY'].startswith(('sk_test_', 'rk_test_'))
    assert active.get('STRIPE_LIVE_VERIFY_NONCE') == nonce
    assert active.get('STRIPE_LIVE_VERIFY_WEBHOOK_SECRET') == candidate['STRIPE_WEBHOOK_SECRET']
    assert candidate['STRIPE_SECRET_KEY'].startswith(('sk_live_', 'rk_live_'))

    def api(path, data=None):
        body = urllib.parse.urlencode(data, doseq=True).encode() if data is not None else None
        req = urllib.request.Request('https://api.stripe.com/v1/' + path, data=body,
                                     headers={'Authorization': 'Bearer ' + candidate['STRIPE_SECRET_KEY']})
        with urllib.request.urlopen(req, timeout=25) as response:
            return json.load(response)

    before = app_snapshot(nonce)
    assert before['test_mode'] and before['verifier_enabled']
    endpoints = api('webhook_endpoints?limit=100')['data']
    matching = [ep for ep in endpoints if ep['url'] == 'https://nuviamy.com/billing/stripe/webhook/'
                and ep['status'] == 'enabled' and ep['livemode']]
    assert len(matching) == 1
    endpoint = matching[0]
    portals = api('billing_portal/configurations?active=true&limit=100')['data']
    portal = next(c for c in portals if c['is_default'] and c['livemode'])
    original_marker = (portal.get('metadata') or {}).get(MARKER, '')
    state.update({'endpoint_id': endpoint['id'], 'original_events': endpoint['enabled_events'],
                  'portal_id': portal['id'], 'original_marker': original_marker})
    state_path.write_text(json.dumps(state)); os.chmod(state_path, 0o600)
    event_added = PROBE_EVENT not in endpoint['enabled_events'] and '*' not in endpoint['enabled_events']
    changed_portal = False
    cleanup_errors = []
    report = {'success': False}
    try:
        if event_added:
            api('webhook_endpoints/' + endpoint['id'], {'enabled_events[]': endpoint['enabled_events'] + [PROBE_EVENT]})
        changed_portal = True
        api('billing_portal/configurations/' + portal['id'], {'metadata[' + MARKER + ']': nonce})
        for _ in range(30):
            after = app_snapshot(nonce)
            receipts = after['receipts']
            if receipts:
                event = api('events/' + receipts[0]['stripe_event_id'])
                if event['pending_webhooks'] == 0:
                    assert event['livemode'] and event['type'] == PROBE_EVENT
                    assert (event['data']['object'].get('metadata') or {}).get(MARKER) == nonce
                    assert before['subscriptions_sha256'] == after['subscriptions_sha256']
                    assert after['test_mode']
                    report = {'success': True, 'stripe_event_id': event['id'], 'live_signature_verified': True,
                              'stripe_pending_webhooks': 0, 'local_subscriptions_unchanged': True,
                              'payments_remain_test': True, 'financial_api_mutations': False}
                    break
            time.sleep(2)
        else:
            raise RuntimeError('No settled signed Stripe delivery received within the probe window.')
    finally:
        # Unsubscribe before clearing the marker, avoiding an unnecessary cleanup event.
        try:
            if event_added:
                current = api('webhook_endpoints/' + endpoint['id'])
                api('webhook_endpoints/' + endpoint['id'], {'enabled_events[]': [e for e in current['enabled_events'] if e != PROBE_EVENT]})
        except Exception as exc:
            cleanup_errors.append('endpoint_events:' + type(exc).__name__)
        try:
            if changed_portal:
                api('billing_portal/configurations/' + portal['id'], {'metadata[' + MARKER + ']': original_marker})
        except Exception as exc:
            cleanup_errors.append('portal_metadata:' + type(exc).__name__)
        try:
            current = read_env(active_path)
            assert current.get('STRIPE_LIVE_VERIFY_NONCE') == nonce
            assert current['STRIPE_SECRET_KEY'] == active['STRIPE_SECRET_KEY']
            lines = [line for line in active_path.read_text().splitlines()
                     if not line.startswith(('STRIPE_LIVE_VERIFY_WEBHOOK_SECRET=', 'STRIPE_LIVE_VERIFY_NONCE='))]
            active_path.write_text('\n'.join(lines) + '\n'); os.chmod(active_path, 0o600)
            subprocess.run(['docker', 'compose', 'up', '-d', '--no-deps', 'web'], cwd=SERVICE,
                           capture_output=True, text=True, check=True, timeout=90)
            healthy = False
            for _ in range(20):
                try:
                    with urllib.request.urlopen('https://nuviamy.com/health/', timeout=10) as health:
                        if health.status == 200:
                            healthy = True
                            break
                except Exception:
                    time.sleep(2)
            assert healthy, "Application health did not recover"
            final = app_snapshot(nonce)
            assert final['test_mode'] and not final['verifier_enabled']
            assert before['subscriptions_sha256'] == final['subscriptions_sha256']
        except Exception as exc:
            cleanup_errors.append('temporary_receiver:' + type(exc).__name__)
        report['cleanup_errors'] = cleanup_errors
        report['temporary_verifier_disabled'] = not cleanup_errors
        state['result'] = report
        state_path.write_text(json.dumps(state)); os.chmod(state_path, 0o600)
        print(json.dumps(report), flush=True)
    if not report['success'] or cleanup_errors:
        raise SystemExit('Webhook proof incomplete; inspect protected state and restore temporary configuration.')


if __name__ == '__main__':
    run()

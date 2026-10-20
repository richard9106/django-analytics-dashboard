# Stripe live webhook verification — 2026-10-15

Actual live Stripe event: `evt_1UQn5VRDhzX5FbDxFnKAEKJp`, type `billing_portal.configuration.updated`, delivered to `https://nuviamy.com/billing/stripe/webhook/`.

The receiver verified the candidate live endpoint signing secret and unique marker, recorded an audit receipt and returned HTTP 200. Stripe reported zero pending deliveries. Subscription fingerprints before and after were identical; no financial API mutations were performed. The application retained its test payment credentials.

Independent cleanup verification confirmed original endpoint event selection and portal metadata restored, temporary secret/nonce removed from active environment, verifier disabled and public health HTTP 200. Protected recovery state remains on the server outside the repository. CI for the receiver passed 549 tests.

This proves live HTTPS delivery and signing-secret compatibility. It does not prove payment settlement or authorize switching billing credentials to live mode.

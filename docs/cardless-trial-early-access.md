# Cardless access

New practices receive 15 days from account creation without a Stripe customer,
card or subscription. The fixed deadline is not extended by checkout cancellation.
At expiry subscription middleware keeps records readable and authorized exports
available, blocks writes, and requires an explicit paid checkout for renewed access.
Stripe checkout has no additional trial; confirming payment starts paid billing.
Existing paid subscriptions and internal practices retain their previous behavior.
Legacy pending checkouts are expired before creating a checkout under this policy.

## Ten private invitations

Ten database slots are created by migration. Issue a private link using:

    python manage.py issue_early_access_invitation SLOT EMAIL

SLOT is 1–10. The command prints a secret link and sends no email. Share it privately
with its intended recipient. Issuing an unused slot again rotates its link; a redeemed
slot cannot be reused. Links expire after 30 days, are email-bound, and only a token
hash is stored. Signup locks the invitation and redeems it once, granting 12 calendar
months from signup (February 29 ends February 28 the following year).

Each invitation covers one internal user in a new practice. Adding or reactivating
additional internal staff requires voluntary paid conversion, which starts ordinary
per-user billing immediately. Client portal accounts are not internal seats. The
invitation is not a public first-ten-signups promotion. No invitations are issued
by deployment and no conversion or charge is scheduled at expiry.

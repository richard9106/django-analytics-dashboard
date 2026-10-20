# Profile settings review — October 20 2026

Local implementation; not a production deployment record.

## Connection status

The shared connection indicator previously required Google status `connected` and Gmail sending enabled. Read-only Gmail and Calendar-only connections could therefore appear incomplete despite an authorized Google account. Navigation now follows the saved Google connection status; the Gmail capability indicator accepts sending or reading. A `needs_reauth` record still requires reconnection and is not presented as connected.

Profile settings displays the saved connected account and selected capabilities, or an explicit reconnect/not-connected state. Optional connections no longer occupy a warning/checklist hero. The sidebar reminder is suppressed on the profile page and elsewhere names only the services that remain unconnected. Rendering does not refresh tokens, request new Google permissions or contact Google.

## Layout and behavior

- Personal details first, followed by subscription and optional connection cards. Page width and spacing are scoped to this screen; narrow screens use a single column.
- Subscription invoices live inside the subscription card, collapsed when empty and expanded when invoices or loading errors exist.
- Practice data export is an owner/admin disclosure, retaining its security note, scopes, formats and authenticated export route.
- Billing actions/invoices remain limited to owners/admins; the view does not fetch Stripe invoices for therapists.
- Invalid profile edits retain the submitted values and reopen the edit dialog with errors. Billing-period changes still require preview before confirmation.

## Validation

32 PostgreSQL tests passed across the new profile connection cases, existing ProfileSettingsViewTests and practice integration tests. Django checks, migration consistency and static collection passed; no new migrations are required.

Browser checks used synthetic accounts at 1920, 1440, 768 and 390 pixels: connected Gmail read access without send permission, responsive layout without horizontal overflow, export disclosure, invalid form behavior, active subscription layout and billing preview gating. Desktop and mobile page images were visually inspected. No real Google/Stripe connection, charge or production record was changed.

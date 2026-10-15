# International professional billing preparation — updated 2026-10-14

Status: preparation for a future paid release, not authorization to charge or use patient data. Public preview terms remain in force. Stripe remains in test mode. The operator's fiscal registration work is outside this change.

## Approved commercial scope and proposed paid wording

The operator has broadened the intended offer: professionals may try and purchase from other countries too. There is no NuviaMy country-based activation block. Capture and retain the purchaser's professional declaration, legal billing name, country and establishment address. Stripe remains in test mode; international commercial availability does not establish that live tax obligations, provider restrictions or clinical requirements have been satisfied in every country.

One complete subscription costs USD 39 per active internal user per month or USD 421 per active internal user per year. Active owners, administrators and therapists count; client portal accounts and deactivated staff do not. Annual price is the stated USD 421, rather than an exact arithmetic promise of a 10% discount. Applicable taxes must be disclosed before payment after their treatment is determined.

New practices can evaluate the preview for 15 days without a payment card. No subscription or automatic charge starts when that period ends. A paid subscription begins only when the purchaser explicitly confirms payment in Checkout; paying early starts billing immediately and does not add another trial. Ten privately invited internal users may receive twelve calendar months of free access under the invitation conditions; that promotion does not automatically convert into a paid subscription.

Paid subscriptions renew for the selected monthly or annual period until cancelled. Changes to active user count or billing period may produce prorated adjustments; display the applicable amount before a purchaser confirms a period change. Team quantity changes currently attempt synchronization; periodic reconciliation and visible failure handling remain pending and must be resolved before promising exact automatic quantity billing.

Cancellation stops the next renewal. Access continues through the last cancellation date shown, until 00:00 UTC on the following day; hours beyond Stripe's paid cutoff are complimentary. Once access expires, authorized record viewing and export remain available subject to the separately published retention policy. Cancellation is distinct from deleting records.

Billing errors and duplicate charges can be reported to support@nuviamy.com for investigation and correction. Other refund requests are reviewed individually, subject to applicable mandatory rights; no universal exclusion of those rights is proposed. Cancellation alone does not promise a prorated refund of a correctly billed period.

The supplier is Richard Andres Marles Bonilla, Calle Paciente Inglés 22, 50019 Zaragoza, Spain. Fiscal identification is supplied from protected configuration and is not copied into this document. Support is support@nuviamy.com. Final invoices must identify both supplier and purchaser, dates, unique numbering, service period, quantity, currency, amounts and the correctly determined tax treatment. Validate a sample invoice and any correction document before live release. A Stripe payment receipt alone is not assumed to satisfy every invoicing requirement.

This draft addresses billing only. It does not authorize processing real clinical records, assert HIPAA compliance or substitute for the remaining provider agreements and clinical release work. Material changes require a new commercial terms version and acceptance evidence; existing preview acceptance is not acceptance of these future paid terms.

## Implemented Checkout collection

- Required billing address on new subscription sessions.
- Optional business tax ID collection, including the supported US business identifier. Do not ask for a Social Security number. Stripe format checking is not proof that a supplied business identifier is valid.
- Existing customers save the address entered in Checkout and, when supplied through business tax ID collection, the legal business name.
- Pending sessions with the old policy are expired and replaced, avoiding reuse of a checkout without these collection settings.
- No automatic tax calculation, tax rate, exemption, live credentials or real charge is introduced.

Optional tax ID entry does not guarantee every customer supplies a legal business name. Required professional/legal-name declaration is now implemented. Country-based purchase restrictions are not requested under the revised international scope.

## Tax decision record and remaining evidence

| Transaction | Working treatment to verify | Evidence/action before charging |
| --- | --- | --- |
| Service to a US business establishment for its professional activity | AEAT's general B2B rule places the service at the recipient; normally outside Spanish VAT, subject to applicable particular rules | Confirm SaaS classification and recipient establishment/status; retain billing and business evidence; validate invoice wording. Do not describe this as a universal 0% VAT rate. |
| US state/local sales tax | No universal result: taxability and registration obligations depend on jurisdiction and nexus | Identify customer states, relevant physical/economic activity and SaaS classification; review authoritative state rules and record the conclusion. US hosting location is not evidence that every jurisdiction is cleared. |
| Professional outside the US | Within the new intended international scope; tax treatment depends on country and business evidence | Review domestic Spanish VAT, EU B2B/business identification and other destination rules separately before live billing. Do not apply the US decision universally. |
| Consumer purchase | Outside the professional-purchase declaration | Review under a separate commercial/tax policy before offering consumer subscriptions. |

Review the Stripe supplier profile and invoice settings: the test account check did not show a business-profile name. Configure the correct issuer identity and validate the resulting invoice, rather than assuming the brand alone identifies the supplier. A Spanish personal NIF must not be submitted as a registered EU VAT number without the applicable registration.

Before publishing paid terms: complete the above tax decisions, purchaser declaration, invoice validation and quantity failure handling; version the final terms and collect acceptance. A separately approved live rollout remains required.

## Sources

- [AEAT — services supplied across borders](https://www3.agenciatributaria.gob.es/Sede/iva/iva-operaciones-comercio-exterior/prestaciones-servicios.html)
- [Stripe — business tax IDs in Checkout and validation limits](https://docs.stripe.com/tax/checkout/tax-ids)
- [Stripe — US sales tax, nexus and jurisdiction differences](https://docs.stripe.com/tax/supported-countries/united-states)

Validation: 71 relevant Django/PostgreSQL tests passed, including existing-customer collection and replacing legacy pending sessions. These tests do not establish fiscal compliance or exercise a live payment.

## Automatic invoice template assignment

`STRIPE_INVOICE_TEMPLATE_ID` selects a template from the same Stripe environment as the API key. When configured, SaaS Checkout assigns it to the existing subscription customer or creates and persists a customer with that template before opening Checkout, so the first subscription invoice uses it. Customer creation uses an idempotency key. Template assignment errors block Checkout with a retry/support message. When the setting is blank, the existing Stripe default behavior remains available for development.

This setting does not apply to Stripe Connect patient invoices. Existing SaaS subscription customers can receive the same customer-level setting without rewriting finalized invoices. Higher-priority invoice/subscription overrides in Stripe still take precedence. Updating this setting does not automatically bulk-update existing customers; the rollout must explicitly synchronize them. A test template ID must be replaced with the correct live-environment ID during a separately approved live rollout.

## International professional pre-Checkout declaration

Before every subscription Checkout, the manager supplies legal billing name, billing country, street address, city and an unchecked professional-purchase declaration. State and ZIP validation apply to United States addresses; elsewhere region/postal code are optional and support letters. Invalid country codes, missing name/address/city or missing declaration are rejected, but selecting a supported international billing country is not a reason to block payment or paid activation. GET displays the form without creating Stripe objects. Draft values remain in the session; the declaration is unchecked on a new visit. Valid submissions are recorded in the append-only practice audit with actor/time and version `international-professional-v1`. With the production invoice template enabled, details are saved to the subscription customer before Checkout.

The form is purchaser-supplied evidence, not independent proof of business status or entitlement to tax exemption. No country activation gate, automatic tax, tax exemption or live key was deployed. US-specific gate implementation was withdrawn before deployment at the operator's request. Current operator facts: works alone from Spain without US staff/office, VPS currently in Europe, possible future New York migration requires a new review.

Before real charges, review the expanded international tax scope rather than assuming all buyers receive the same US B2B treatment. Free preview remains cardless and independent of billing country. Local acceptance tests cover Spanish, British and Irish addresses, as well as US state/ZIP validation.


## Publicación de condiciones — 2026-10-15

Las condiciones comerciales acordadas están publicadas en `/terms/#subscription-conditions`, versión `2026-10-15-commercial-v1`, con aceptación independiente antes de Checkout. La publicación mantiene explícitos los límites actuales: pagos de prueba y datos ficticios, tratamiento fiscal internacional y presentación con/sin impuestos pendientes. Por ello no constituye la apertura de cobros reales ni sustituye los contratos/procedimientos clínicos pendientes.

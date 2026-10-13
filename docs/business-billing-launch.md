# US professional billing preparation — 2026-10-13

Status: preparation for a future paid release, not authorization to charge or use patient data. Public preview terms remain in force. Stripe remains in test mode. The operator's fiscal registration work is outside this change.

## Approved commercial scope and proposed paid wording

Initial customers are therapists and clinics established in the United States purchasing for their professional activity. Consumer purchases and purchases for establishments outside the US are outside the initial offer. Before enabling live checkout, capture and retain the purchaser's professional declaration, legal billing name and US establishment address; current Checkout address collection alone does not enforce this restriction.

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

Optional tax ID entry does not guarantee every customer supplies a legal business name. Required professional/legal-name declaration and geographic restriction remain a separate release task.

## Tax decision record and remaining evidence

| Transaction | Working treatment to verify | Evidence/action before charging |
| --- | --- | --- |
| Service to a US business establishment for its professional activity | AEAT's general B2B rule places the service at the recipient; normally outside Spanish VAT, subject to applicable particular rules | Confirm SaaS classification and recipient establishment/status; retain billing and business evidence; validate invoice wording. Do not describe this as a universal 0% VAT rate. |
| US state/local sales tax | No universal result: taxability and registration obligations depend on jurisdiction and nexus | Identify customer states, relevant physical/economic activity and SaaS classification; review authoritative state rules and record the conclusion. US hosting location is not evidence that every jurisdiction is cleared. |
| Consumer or non-US customer | Outside approved initial commercial scope | Prevent purchase or review under a separate tax/terms decision; current Checkout does not block these addresses. |

Review the Stripe supplier profile and invoice settings: the test account check did not show a business-profile name. Configure the correct issuer identity and validate the resulting invoice, rather than assuming the brand alone identifies the supplier. A Spanish personal NIF must not be submitted as a registered EU VAT number without the applicable registration.

Before publishing paid terms: complete the above tax decisions, purchaser declaration, invoice validation and quantity failure handling; version the final terms and collect acceptance. A separately approved live rollout remains required.

## Sources

- [AEAT — services supplied across borders](https://www3.agenciatributaria.gob.es/Sede/iva/iva-operaciones-comercio-exterior/prestaciones-servicios.html)
- [Stripe — business tax IDs in Checkout and validation limits](https://docs.stripe.com/tax/checkout/tax-ids)
- [Stripe — US sales tax, nexus and jurisdiction differences](https://docs.stripe.com/tax/supported-countries/united-states)

Validation: 71 relevant Django/PostgreSQL tests passed, including existing-customer collection and replacing legacy pending sessions. These tests do not establish fiscal compliance or exercise a live payment.

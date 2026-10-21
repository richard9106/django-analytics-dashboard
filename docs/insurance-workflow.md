# Practice insurance workflow

Implemented October 21, 2026. This document describes the code change; production rollout is separate.

1. Under Settings → Insurance, expand Available payer catalogue and enable the insurers your practice uses. My payers contains enabled catalogue payers and your custom payers. Disabling a catalogue payer changes only this practice’s selection. Custom payers can be disabled through Edit. The legacy removal endpoint now deactivates rather than deleting configuration/history.
2. Add contracted rates for an enabled payer, state and service code. Zero is a valid rate. Disabled rates or payers are excluded from suggestions; historical references remain available for inspection/editing.
3. In a client profile, select Insurance billing, link an enabled payer, and enter the rate state, member ID and expected client share when known. Existing free-text insurance names are retained as legacy references and are never automatically matched to a catalogue entry. A disabled payer can remain on an existing client but cannot be newly assigned.
4. Create an invoice from Billing or its appointment. Select the client and service code, then explicitly load the insurance suggestion. The suggestion fills the matching reference charge and known client share; unknown shares must be confirmed manually. This is not an eligibility check. No matching rate means manual entry, not an invented price. Insurance packages are excluded from this individual-service allocation flow.
5. Review the charge and client share before saving. Insurance allocation is charge minus client share. The stored payer name, service/state and contracted reference are retained with the invoice; later catalogue/rate changes do not recalculate them. A draft with recorded payments cannot change its allocation through the invoice form. Published invoices retain their existing non-editable behavior.
6. Record the client and insurer payments separately. For a $120 charge with $20 client share, the portal offers $20 and leaves $100 allocated to insurance. Manual payment checks cap each side at its remaining balance, with a locked recheck during save. Stripe’s signed client-payment events on insurance invoices create a payment idempotently; the invoice is settled only when all recorded payments cover the charge. No automatic insurance reimbursement or contractual write-off is created.

## Migration and history

`billing.0013` adds local selection and invoice allocation fields. `billing.0014` enables catalogue payers already referenced by the practice’s rates, preserving existing configuration without enabling the full catalogue. `clients.0004` adds structured insurance fields. Existing clients and invoices keep their old self-pay behavior until explicitly configured; no legacy insurance name is fuzzy-matched and no previous financial allocation is inferred. Existing invoice totals/payment records are not rewritten.

JSON/ZIP exports include structured client insurance, payer selections and rates, invoice payer-name/rate snapshots and client shares. Deactivation retains old references and monetary records.

## Scope

This phase does not enroll clinicians, verify coverage, transmit claims, import ERA/EOB, calculate deductibles/coinsurance from a policy, process secondary insurance or apply contractual write-offs. An expected client share must be reviewed against actual responsibility. If the practice changes the total from the suggested contracted reference, the invoice uses the reviewed total; the original reference remains identifiable. Neither an insurer name nor a Payer ID establishes an electronic connection.

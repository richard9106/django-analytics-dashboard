# Session documentation workflow

Appointments supports Calendar and List displays. List loads 25 appointments per
page, preserves search and filter state, and offers documentation filters. Admins
and owners see their practice; therapists see only their assigned appointments.
The same scope applies to appointment URLs, recurring-session actions, note forms,
clinical notes, dashboard session data and client-profile session summaries.

Ended appointments without a signed note have a light orange row plus “Note missing”
or “Signature pending”. Future appointments, cancellations and no-shows are not
flagged. A draft record is treated as an existing note, including an empty draft,
so the workflow offers review rather than creating a duplicate.

Create note from the list preselects the session, client and therapist. After saving,
the user reviews the note before signing. Only its responsible therapist with
clinical edit permission may sign, after the scheduled session end. Confirmation,
a nonempty note and a matching review digest are required. A stale review is refused.

Signatures are separate, one-to-one records containing the authenticated signer,
a name snapshot, timestamp and SHA-256 digest of the note content and associations.
Signing a draft first locks its content; signing a legacy locked note leaves the
original row untouched. Existing locked notes remain unsigned until explicitly
attested. No automatic signatures or historical signature backfill are performed.

Both finalized note content and signature records are protected against SQL updates,
deletes and truncation. Signature records are included in clinical exports. Corrections
to finalized content require a separate documentation record; this change does not
introduce an addendum editor.

Protected test teardown disables truncate guards only in disposable `test_` databases.
Production guards are never disabled by application code.

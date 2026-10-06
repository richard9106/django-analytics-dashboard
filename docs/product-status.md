# Product Status And Gaps

This document captures the current product state after the recent UX, billing, and availability work. It is meant as a practical handoff checklist, not a full product spec.

## Recently Completed

- Converted major dense workspaces to calmer table/tree layouts with final action menus.
- Added reusable row-action and modal behavior in the shared sidebar partial.
- Hardened clinical note locking so locked notes remain immutable.
- Tightened billing/settings permissions and portal access reset permissions.
- Added invoice publishing, payment ledger behavior, and portal invoice visibility.
- Added portal secure messaging and appointment change requests.
- Added Google Calendar sync issue visibility.
- Added recurring appointment controls and package usage rules.
- Added CI test/deploy workflow with deployment health checks.
- Switched SaaS subscriptions from fixed Solo/Group/Clinic tiers to per-active-user pricing.
- Added date-specific availability overrides managed directly from the calendar.

## Current Availability Behavior

- The calendar is now the primary place to manage availability.
- Settings no longer exposes Availability in the sidebar.
- The old weekly availability page remains available as a baseline fallback, but normal use should happen from the calendar.
- Date-specific availability can set:
  - available hours for one date;
  - available hours across a date range;
  - full-day unavailable dates;
  - unavailable time ranges inside an otherwise available day;
  - weekly or monthly repeated overrides.
- Date-specific availability overrides the weekly baseline.
- Appointment creation and public booking requests both validate against the same availability helper.
- Clicking an unavailable time in Day/Week calendar opens the availability modal first, prefilled with that date/time range.

## Current Subscription Behavior

- Public pricing presents one per-active-user plan.
- Billable users are active owners, admins, and therapists.
- Client portal users and deactivated staff do not count.
- Stripe Checkout, billing-period changes, and proration previews pass subscription quantity.
- Team create/deactivate/reactivate actions attempt to sync Stripe subscription quantity.
- Existing `solo`, `group`, and `clinic` subscription slugs remain in code for compatibility with existing records and URLs.

## Current Insurance Module

- Insurance settings are practice-scoped.
- Practices can manage payer records, payer IDs, states, service codes, labels, reimbursement amounts, and active/inactive status.
- These records support billing/superbill-style workflows and avoid cross-practice data sharing.
- The module does not yet submit claims or verify benefits electronically.

## Important Gaps

- Stripe quantity reconciliation is best-effort only; add a management command or scheduled job to detect local/Stripe quantity drift.
- Calendar availability overrides can be replaced by saving the same date/range, but there is no dedicated list/edit/delete UI for existing overrides yet.
- Availability is practice-wide, not therapist-specific. If individual clinicians need different schedules, add therapist-scoped overrides later.
- Public booking is validated against availability, but there is not yet a client-facing slot picker that only shows available times.
- Insurance does not yet include claims submission, ERA/EOB import, eligibility checks, or denial management.
- The goal is US clinical use with demonstrable HIPAA compliance. The first security delivery upgrades Django LTS, guards production startup, and strengthens CI/deployment. MFA, BAA/vendor validation, protected audit trails, retention, incident response, and operating policies remain prerequisites for real patient data; see `clinical-readiness-us.md`.

## Recommended Next Work

1. Complete the P0 clinical-readiness controls and operating evidence in `clinical-readiness-us.md` before a pilot with real patient data.
2. Add a compact availability override inspector on the calendar so users can review and delete date-specific overrides.
3. Add Stripe subscription quantity reconciliation and an admin/monitoring warning for failed quantity sync.
4. Improve public booking with available-slot selection instead of free-form date/time entry.
5. Add therapist-specific availability if multi-provider scheduling becomes important.
6. Expand insurance from payer/rate settings into claim lifecycle tracking.

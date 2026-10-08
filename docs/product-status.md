# Product Status And Gaps

This document captures the current product state after the recent UX, billing, and availability work. It is meant as a practical handoff checklist, not a full product spec.

## Recently Completed

- Made Treatment Plans fill the available workspace width while preserving its filter sidebar and mobile stacking. Compacted Intake into separated client-form rows and a smaller template library, with scoped typography, status/actions, preview/edit controls and responsive layouts reviewed by the specialized UX designer.

- Ordered Overview as metrics, charts, billing, then appointments/tasks; conditional first steps remain at the top. Increased authenticated session inactivity timeout to one hour, shared by server enforcement and the browser countdown.

- Compacted Overview typography, task rows and billing tables following specialized UX review. First steps appear above the workspace actions only while permitted setup actions remain incomplete. Added a revenue line/area, session columns, session-status donut and invoice-status horizontal bars using scoped six-month data, accessible numerical summaries and truthful zero states.

- Redesigned Overview with actionable KPI cards, independent bounded appointment/task scroll regions and billing balances plus recent invoice links before trend charts. Assigned tasks open a tenant-scoped detail page; automatic follow-ups link to their permitted source workspaces. Pending-item counts include all assigned tasks while the dashboard preview is capped at 50, and financial balances subtract partial payments and exclude drafts/voids. Restricted modules are omitted from dashboard data and cards. Six-month performance uses two grouped queries rather than twelve monthly queries. Specialized UX review covered hierarchy, keyboard access, mobile layout and the task flow.

- Improved scheduling with a weekly Agenda alternative, explicit single-session cancellation that retains records, touch/keyboard rescheduling and client access from sessions. Calendar create/edit/delete and recurring actions keep a validated calendar return path; client selection is explicit and a sole therapist is preselected. Creating recurring sessions rolls back the entire series on a later conflict, returns the bound form and syncs only after successful saving. Calendar modal dates are prepared before the shared dialog handler, grid hit testing measures its header and rescheduling checks the actual duration. Permissions, 44px calendar controls and optional Google UI were reviewed by the specialized UX designer.

- Replaced ambiguous sidebar glyphs with consistent 24px inline SVG icons, reviewed by the specialized UX designer. Compact navigation retains accessible names and hover titles; request counts fit as corner badges and mobile restores the inline layout. Icons require no external library, requests or JavaScript.

- Added a shared, route-based breadcrumb hierarchy across all workspace modules, profile/security and authenticated help pages. Patient records, intake templates, invoice edits and session-linked forms retain their validated parent context. Ancestor links follow workspace permissions, only the final item is current, labels are escaped, and the mobile trail scrolls horizontally. The template tag uses already-scoped view objects without additional record queries or stored browsing history. Specialized UX review guided layout and keyboard targets.

- Intake now has a paginated assignment queue with patient/form search, status totals and filters, a template library with question previews and permission-aware editing, and a separate numbered response review page. Template changes apply only to future assignments: packet content is snapshotted on assignment and existing responses are preserved by a data migration. Invalid create/edit/assign forms retain entered values and field errors; pending packets cannot be marked reviewed and repeat review actions preserve the original reviewer/date. Specialized UX review retained native dialogs, compact checkboxes and mobile layouts.

- Diagnosis creation/editing now opens native dialogs inside the patient record, reviewed by the specialized UX designer. Patient context stays fixed, the checkbox uses compact sizing with a large clickable label, and validation errors preserve entered values and reopen the dialog. Standalone fallback pages retain diagnosis-specific copy and corrected Boolean controls.

- Moved diagnosis management into the patient workspace and removed the practice-wide diagnosis panel/create/edit dialogs from treatment plans. Plan diagnosis choices follow the selected patient in both browser and server validation. Existing linked inactive diagnoses remain selectable on edit. Options load only on opening a form and are reused within the page; a CI JavaScript check verifies switching patients, late responses, existing inactive links and caching.

- Connected session → note → invoice through calendar session dialogs and edit pages. Tenant-checked session links prefill note client/therapist/appointment and invoice client/appointment; saving a linked record returns users with calendar edit permission to the session. Review notes/invoices links filter by session, and invoice review clearly shows the active filter. Existing create permissions and payment flows are retained; creating a draft does not collect a payment.

- Added Review availability to the calendar: a collapsible list of date-specific changes for the visible period, tenant-scoped single-record editing, and removal with confirmation. Edit/remove actions follow workspace permissions and preserve the calendar return URL. Other dates/ranges and existing appointments are not modified by single-record editing. No new services or additional list queries are needed.

- Simplified first steps for solo therapists and clinics: client creation no longer requires Gmail or Stripe Connect. Connections remain optional for email delivery and online client payments; payment flows retain provider checks. Daily appointments/tasks appear before charts, with links to client records and session management. Existing lightweight server-rendered pages and permission checks are retained.

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
- Calendar availability changes can be reviewed for the visible period through Review availability. Users can edit a single record or remove it, retaining calendar filters; creating date/range changes still replaces existing changes for the affected dates.
- Availability is practice-wide, not therapist-specific. If individual clinicians need different schedules, add therapist-scoped overrides later.
- Public booking is validated against availability, but there is not yet a client-facing slot picker that only shows available times.
- Insurance does not yet include claims submission, ERA/EOB import, eligibility checks, or denial management.
- The goal is US clinical use with demonstrable HIPAA compliance. The first security delivery upgrades Django LTS, guards production startup, and strengthens CI/deployment. Staff MFA, recovery, shared rate limits, and session expiry/revocation are implemented with security boundary tests. BAA/vendor validation, protected audit trails, retention, incident response, and operating policies remain prerequisites for real patient data; see `clinical-readiness-us.md`.

## Recommended Next Work

UX decisions and interface changes should be delegated to the specialized NuviaMy UX designer in `.opencode/agent/nuvia-ux-designer.md`, as requested by the owner. Include contextual placement, checkbox sizing, validation feedback, keyboard behavior and mobile layout in the review.

The owner prioritizes workflow completeness and an intuitive interface during pre-client development, using the existing lightweight architecture on the VPS. Preserve current protections; defer additional security infrastructure until the usability work is resolved. Clinical-readiness criteria remain prerequisites for a real-patient pilot.

1. Review the patient → appointment → session note → invoice → follow-up journey, preserving context and making the next action clear.
2. Availability review/edit/remove is implemented; continue simplifying calendar workflows and form feedback.
3. Improve solo/team scheduling, including therapist-specific availability when required.
4. Improve public booking with available-slot selection instead of free-form date/time entry.
5. Add Stripe subscription quantity reconciliation and a warning for failed quantity sync.
6. Complete the clinical-readiness controls and operating evidence in `clinical-readiness-us.md` before a real-patient pilot; expand insurance workflows as a separate product scope.

## Clinical readiness: protected evidence

Audit events are append-only through Django/admin and protected by PostgreSQL triggers. Finalized notes reject bulk and direct SQL mutations; clinical parent relationships prevent cascading removal of history. Sensitive-module reads and denied access now have metadata-only access events. See [clinical readiness](clinical-readiness-us.md) for coverage limits, privileged-database risks, outstanding retention/contractual work, and [proposed launch markets](us-launch-markets.md). These controls do not mean the product is cleared for clinical use.

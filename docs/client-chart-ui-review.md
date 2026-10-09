# Client chart review — October 9, 2026

The original two-column layout stretched demographic information to match the combined height of portal, billing and clinical records. This produced a large empty area and made individual records difficult to reach.

## Reference patterns

- [SimplePractice client Overview](https://support.simplepractice.com/hc/en-us/articles/5357432054541-Navigating-the-client-Overview-page): chronological activity, contextual information, and distinct Billing and Files sections.
- [TherapyNotes patient comments](https://support.therapynotes.com/hc/en-us/articles/30661199836443-Add-a-Comment-on-a-Patient-File): information belongs to the relevant patient-chart section and visibility depends on staff roles.

These informed the organization; NuviaMy retains its existing brand and workflows.

## Result

Server-rendered Overview, Clinical, Billing and Documents navigation keeps the client's identity visible and works without JavaScript. Overview shows the next scheduled appointment, session history and a compact independent information rail. Clinical groups diagnoses, notes and treatment plans. Billing and Documents provide links to existing records. Diagnosis validation and the client edit dialogs remain intact.

Sections and actions follow existing permissions. Disallowed section URLs fall back to Overview without loading restricted records. Billing balances account for partial payments with a grouped query. Appointment creation preselects the client and primary therapist only after checking practice ownership.

Browser review used fictional local records at 320, 390 and 1280 pixels, including navigation, diagnosis dialog and narrow billing-table scrolling. Physical mobile-device behavior remains outside this browser review. Billing and Documents show the latest 20 records; clinical lists retain eight recent notes/plans and the diagnoses list. Overview shows up to eight past sessions.

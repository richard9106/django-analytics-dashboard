# Google OAuth identity minimization — 20 October 2026

Removed the unused `profile` base scope. NuviaMy only consumes the Google account email for identifying the connected integration. Base scopes are now `openid email`; additional permissions remain those selected for individual integrations.

PR 68: https://github.com/richard9106/django-analytics-dashboard/pull/68
Tested head f4306eb20c187e32e0e377b7924e314aa15d52c7; PR CI 39433887252 succeeded. Merge 22a5f30e0297024d030e39aa6cabf2f388959379 has the identical tree. Main CI/deployment 39434627167 completed successfully: full tests and AWS production deploy passed; legacy deployment skipped. Live AWS checkout matches 22a5f30e0297024d030e39aa6cabf2f388959379.

The existing connect-flow test now asserts the exact outgoing scope set, including the selected Calendar/Gmail features and the minimal identity scopes. Targeted test passed locally; the complete suite passed in PR CI.

Existing Google grants/tokens are not revoked or modified by the change. For verification recording use a fresh test authorization; older Google grants can retain previously approved permissions. No demonstration video has been recorded or uploaded by this work.

Production verification generated the Calendar authorization request in the running application without sending Google requests or modifying existing connections. Its exact scopes were openid, email and https://www.googleapis.com/auth/calendar.events; profile is absent. Public health returned 200 with a valid TLS certificate.

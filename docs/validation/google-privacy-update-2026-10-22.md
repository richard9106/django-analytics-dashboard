# Google privacy disclosures — 22 October 2026

Policy version: 2026-10-22-v4. Prepared in code; publication is a separate deployment step.

The public privacy notice now documents the current optional account, Gmail send/read, Calendar and Drive flows, stored credentials and sync metadata, practice access, processors, protection, retention, deletion requests and the limits of disconnecting. It includes the affirmative Google API/Workspace Limited Use commitment and restrictions on advertising, sale, generalized AI training and operator human access. A changed Google-data purpose requires notification and consent before that use; this update describes existing functionality and does not expand scopes or authorize a new purpose.

The integration screen presents the disclosure visibly immediately before Connect Google, with links to the full policy and Google third-party connection management. Privacy is also linked in the workspace sidebar and Google workspace. Disconnect behavior is documented accurately: active credentials are cleared; Google grants, external copies and retained backups are not claimed to be automatically erased.

Privacy versioning affects new notice/acceptance records. Previously accepted agreement snapshots and receipts remain unchanged; the standard DPA/BAA offer version is not changed by a privacy clarification.

Validation: public-page and in-product disclosure checks, existing Google OAuth tests and immutable agreement snapshot tests. Run against temporary PostgreSQL to include the PostgreSQL-only rehearsal-isolation test. SQLite cannot run that existing test's current_database() query.

Remaining verification work: confirm domain ownership and policy URL in Google Console, declared/requested scopes and any restricted-scope assessment or exception. The optional gmail.readonly capability still exists. Review Drive's use case against Google's permitted-use policy. These changes do not establish Google approval or a completed security assessment. No OAuth permissions, existing grants or tokens are changed by this update.

Sources:
- https://support.google.com/cloud/answer/13806988
- https://developers.google.com/terms/api-services-user-data-policy
- https://developers.google.com/workspace/workspace-api-user-data-developer-policy
- https://developers.google.com/workspace/gmail/api/auth/scopes

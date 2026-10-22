# Calendar OAuth verification preparation

Google Cloud project: nuviamy. Current submitted Calendar scope: calendar.events.
Proposed scope: https://www.googleapis.com/auth/calendar.events.owned.

The app reads upcoming events and creates, patches and deletes appointment occupancy events on the primary calendar only. Google documents owned scope as allowing these operations on calendars the user owns. Read-only/freebusy cannot write occupancy events; app.created applies to secondary calendars created by the app, rather than the existing primary calendar.

Reference: https://developers.google.com/workspace/calendar/api/auth

## Isolation

GOOGLE_CALENDAR_OWNED_SCOPE_PRACTICE_IDS is empty by default. Only server-configured practice IDs request the narrower scope on a fresh OAuth connection. IDs are not accepted from request parameters. Other practices keep their existing scope; saved tokens and integrations are not migrated. Remove an ID to restore the previous scope for subsequent connections. Existing grants are not revoked automatically.

This is a preparation change, not evidence of successful live authorization or API compatibility. Before submitting the verification video, configure the matching scope in Console, enable only the confirmed fictional demo practice, authorize the demo connection, and demonstrate real list/create/update/delete operations. Keep ordinary production traffic unchanged until verification/rollout is ready.

## Proposed English justification

NuviaMy optionally connects the user's primary Google Calendar to display upcoming events and synchronize appointment occupancy blocks. We request calendar.events.owned instead of calendar.events because we do not need access to calendars owned by other users. We read events and create, update and remove occupancy blocks on the primary calendar. Read-only and free/busy scopes cannot write these blocks. calendar.app.created covers secondary app-created calendars and cannot synchronize the existing primary calendar. Blocks contain a generic “Reserved time” title and start/end times, without client names, diagnoses or clinical notes.

## Validation

18 IntegrationSettingsTests passed, including exact requested scope sets for an allowlisted practice, a different practice and the empty default. Real Google API validation and the recording remain pending.

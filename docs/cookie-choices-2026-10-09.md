# Browser choices and public footer

The public navigation no longer contains Cookies. Marketing and support pages share a footer with product, support, privacy, cookie policy, and Cookie settings links.

Essential session and CSRF cookies remain available for authentication and protected forms. The guided-tour completion flag is optional local storage: it is read and written only after accepting preferences. Choosing Essential only removes any previous tour flag. Completing the tour without consent is remembered only during the current page visit. The separate choice record lasts 180 days; expired, malformed, or older-version records prompt a new choice. Blocked browser storage does not break the page.

`node ops/check_cookie_choices.cjs` covers consent gating, persisted acceptance/rejection, revocation, expiry, malformed storage, and disabled storage. Django checks cover public footer and legal page rendering. Browser checks cover acceptance, rejection, reopening, desktop, and 320/390 px layouts with no horizontal overflow and 44 px choice controls.

The privacy notice describes current processing. It is not the completed launch policy: the operator identity, jurisdiction, public contact details, retention schedule, and applicable rights still need confirmed business/legal information. No operator identity or clinical certification claims were invented.

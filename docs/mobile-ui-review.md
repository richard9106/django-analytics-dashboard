# Mobile UI review — October 8, 2026

Reviewed the local application with fictional practice, client, billing and portal records in browser viewports of 320, 390, 768 and 1280 pixels. This is responsive browser testing; physical-device keyboard and platform-specific behavior still need device testing.

## Changes

- Messages uses a 52-pixel circular button at the lower right on phones, with an accessible label, unread badge and safe-area spacing. The conversation panel fits within the viewport.
- Reduced workspace, panel and form spacing and scaled headings for phones. Actions wrap into compact grids and interactive controls have 44-pixel targets.
- Form text is at least 16 pixels to avoid automatic input zoom on iOS.
- Fixed table labels escaping their horizontal scroll containers on phones and tablets. Long text wraps and wide tables and permission matrices scroll locally.
- Kept the setup reminder inside the expanded mobile navigation and restored the client portal profile menu, including sign-out.
- Improved portal message actions, portal forms, authentication and signup layouts.

## Coverage

Main workspace: dashboard, clients (list, detail, create, edit), calendar, appointment forms, tasks (list and detail), billing and invoice/payment/package forms, documents, clinical notes, treatment plans, intake and template editing, requests, profile, team, security, integrations, availability, insurance, session packages, client portal settings and help.

Public pages: home, features, pricing, product landing pages, help/contact, cookie policy, public booking, signup and password recovery.

Client portal: overview, profile/sign-out menu, messages and conversation dialog, intake response form and appointment change-request dialog. Forms and menus were opened without sending messages or submitting clinical changes.

No document-level horizontal overflow remained in the checked narrow layouts. Billing and Documents were rechecked at 768 pixels after the final table fix. Desktop dashboard and portal layouts retained their desktop message button and had no horizontal overflow.

This review covers representative records and common routes; it does not exhaust every permission combination, empty/error state or device/browser combination.

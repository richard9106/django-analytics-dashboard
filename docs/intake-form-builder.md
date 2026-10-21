# Client form builder

Open Client forms → New template, or Edit template. Each form has a name, an introduction and availability for new assignments. Add named pages, optional page instructions and questions; move pages and questions up/down or move a question to another page. Questions fold to keep longer forms manageable. Preview form shows the client-facing questions and controls without saving answers.

Answer types: short text (500 characters), long text (10,000 characters), single choice, multiple choice, dropdown, and yes/no. Every question can be required or optional and can have help text. Selection types have 2–50 distinct options. Forms allow up to 20 pages and 100 questions; every page must contain a question. Labels, instructions and options are plain text, escaped at rendering, not executable HTML.

The portal progressively enhances the form with page progress, Previous/Next buttons and validation before advancing. Answers remain in the current document while navigating; they are submitted together at the final step. No response draft is stored in browser storage. Without JavaScript, all pages remain visible and the server validates the full submission. Required multiple choice means at least one selected option. Staff see multiple selections as separate lines.

## Compatibility and evidence

The existing `questions` JSON list remains the persisted format. Builder-created entries carry `_builder_version: 1`, stable question/page IDs, type, required flag, help text, options and page title/instructions. No schema migration or rewrite of historical data is needed. Legacy strings and older dictionaries are presented as one page of required long-text answers, retaining the previous portal behavior. The text-line POST format remains supported for compatibility and preserves matched legacy metadata.

Assignments already deep-copy template content into `template_snapshot`. All response fields and pages are derived from that snapshot; editing or reordering the source template only affects future assignments. Answer keys remain `question_N` within the frozen assignment, preserving existing exports and legacy answers. Multiple-choice answers store a JSON list, while staff response rendering uses separate lines.

All schema and answer constraints are validated server-side. Choice submissions are checked against the assigned options; unknown types, duplicate IDs/options, malformed payloads and excessive sizes are rejected. Template ownership, client assignment access, staff permissions and CSRF follow the existing protected routes. A client cannot read or submit another client's form.

Validation: `apps.portal.test_intake_builder` covers schemas, typed answers, optional/required behavior, editing snapshots, escape handling, client access and actual portal submission. Existing portal tests cover legacy forms and assignment workflows. Browser verification covers changing types/options, page ordering, preview, required selection validation, retaining answers across pages and mobile layout.

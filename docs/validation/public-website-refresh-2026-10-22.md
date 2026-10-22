# Public website refresh — 22 October 2026

Prepared for review; not deployed by this change.

## Visitor-facing changes

- Shorter homepage: More time for care. Less time on admin. Trial CTA and 30 days/no-card information are visible above a real product preview.
- Dashboard, scheduling and intake screenshots use the existing fictional NuviaMy demonstration practice, not production client records. They are labelled as fictional. WebP assets are 43–54 KB each and preserve the original 1265 × 712 size. They were sourced from the locally prepared `/tmp/nuviamy-demo-{overview,appointments,forms}.jpg` screenshots previously used for the product tour video. Billing's older screenshot with clipped columns was not used.
- Home and Features have a linked product walkthrough. Five product guides now include practical examples, specific questions and cross-links. The billing guide explicitly excludes electronic claims, eligibility verification and ERA import; trial and optional Google/Stripe requirements are explained.
- Removed the visible keyword cloud and unused meta keywords, replaced developer-oriented copy, and removed the outdated R2 preparation reference from Features.

## SEO implementation

All 14 public pages use one metadata partial for title, description, canonical, Open Graph and Twitter. The 1200 × 630 social image was rendered from an HTML/CSS brand card with the actual fictional dashboard capture. Marketing styles are separately scoped and are not loaded by app pages. Public assets use the existing Django static manifest, allowing versioned asset caching. Product images reserve dimensions; non-hero images are lazy-loaded.

Home's SoftwareApplication offer includes the visible $39 monthly price and currency; Pricing includes monthly and annual offers. No reviews or ratings were fabricated, and rich-result eligibility is not claimed. The sitemap includes the 14 public pages without invented modification dates. Help searches and contact-success variants are noindex/follow and canonicalize to the base page.

PublicWebsiteCanonicalMiddleware permanently redirects GET/HEAD requests for recognized public website pages from www.nuviamy.com to https://nuviamy.com, preserving query strings. It does not redirect POST requests or application paths and does not change local development hosts. This uses the application layer because a tracked production Nginx site configuration is not present in the repository.

## Validation

- 62 tests discovered across dashboard, legal acceptance and standard agreement suites: 61 passed, one PostgreSQL-only test skipped on SQLite. The complete CI suite remains required before merge/deploy.
- Browser: 14 pages × three viewport sizes (1440, 768 and 390 px), 42 checks with one h1 per page, no horizontal overflow and no broken loaded images. Evidence is in the adjacent responsive.json.
- Local HTTP check: all 14 pages and nine referenced static assets returned 200.
- collectstatic, Django system checks and whitespace checks passed.
- Desktop/mobile review captures: `/tmp/nuviamy-website-new-desktop.jpg`, `/tmp/nuviamy-website-new-mobile.jpg`; product tour `/tmp/nuviamy-website-product-tour.jpg`.

Search Console submissions, actual index coverage and field Core Web Vitals remain external verification tasks. No search ranking or performance score is asserted. No new analytics/cookies were introduced. Accepted legal snapshots remain immutable; public metadata changes do not rewrite stored acceptances.

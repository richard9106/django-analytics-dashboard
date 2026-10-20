# Live subscription billing activated — 2026-10-15

Operator explicitly authorized real billing in this conversation. Production switched at 12:29 UTC after main commit `118c0f3fd5d627bdd88636e1049c2bfd8a846ac5` passed CI and deployed (run `38734038156`, 554 tests).

Validated real USD prices: 39 monthly (`price_1UPooARDhzX5FbDxO0A0glpk`) and 421 yearly (`price_1UPooARDhzX5FbDx6EEKmxyS`) per active internal user. Live invoice template `inrtem_1UQ7CDRDhzX5FbDxSoO3tdVM`; live API/public keys and verified real endpoint signing secret loaded from protected configuration. No secret values are stored here.

Two sandbox-backed local subscriptions were archived privately and detached. Existing complimentary workspace access and local trials were preserved; no sandbox paid status was treated as a real paid subscription. The old test endpoint pointing to production was disabled. Ten invitation records remain in place.

Protected pre-switch configuration, billing snapshot and database dump are held outside Git under `/home/deploy/backups/nuviamy/config/live-cutover-20261015T122814Z`. An append-only platform audit records the separation.

Production health returned HTTP 200. Monthly and yearly pre-Checkout forms returned HTTP 200 with real-mode notices, current terms acceptance required, and no Stripe object creation. Every plan maps to the verified live prices. Zero pending sandbox Checkout sessions remain. No charge was created for validation.

This activates commercial billing. Real clinical-data use remains subject to the existing separate launch requirements and published fictional-data preview restriction. Cardless 15-day trials and private invitation access do not convert automatically into charges.

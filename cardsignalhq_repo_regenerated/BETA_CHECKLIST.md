# CardSignal — Closed Beta Checklist

Use this checklist before inviting collectors to a closed beta. Readiness is determined by quality gates, not feature count.

## Data & Intelligence

- [x] MLB real data (performance, weekly intelligence, leaderboards)
- [ ] NFL real data (UI shows Coming Soon — not ready for collector invites)
- [ ] NBA real data (not ready — do not invite NBA-only collectors yet)
- [x] Stable Scouting Reports with honest pending states
- [x] Stable Card Reports (nested in Scouting Report flow)
- [x] No fabricated intelligence in live report paths
- [x] Evidence and freshness indicators on reports
- [x] CardSignal Scores include algorithm version metadata
- [x] Universal Search (leaderboard + backend MLB pool)

## Product Surfaces

- [x] Signal Center homepage intact
- [x] Scouting Report modal (desktop + mobile drawer)
- [x] Card Report navigation from Scouting Report cards
- [x] Hash routing for player/card deep links
- [x] Browser back/forward restores modal state
- [x] Watchlists (authenticated)
- [x] Alerts and notification center (authenticated)
- [x] Authentication (email/password via Supabase)

## Beta Operations

- [x] Beta Feedback submission (`POST /api/beta-feedback`)
- [x] Feedback stored privately with RLS (no public reads)
- [x] Version/build visible to testers (footer)
- [x] Beta changelog accessible from version label
- [x] Internal beta-readiness audit (`scripts/run_beta_readiness_audit.py`)
- [x] Admin-protected feedback review (`GET /api/admin/beta-feedback`)
- [ ] Privacy / Terms pages
- [ ] Closed-beta invite workflow documented
- [ ] Support workflow for triaging feedback
- [ ] Product analytics instrumentation
- [ ] Onboarding guide for first-time collectors

## UX & Quality Gates

- [x] Loading, empty, and safe error states on major surfaces
- [x] Mobile support without horizontal overflow
- [x] Safe collector-facing errors (no raw JSON/stack traces)
- [x] Modal keyboard-close and focus restoration
- [x] Beta Feedback button does not obstruct mobile controls

## Pre-Launch Verification

1. Run `python scripts/run_beta_readiness_audit.py` — target `READY` or `READY_WITH_WARNINGS`
2. Run `python -m unittest discover -s tests -p 'test_*.py'`
3. Run `node tests/test_beta_feedback.js` and `node tests/test_routing.js`
4. Manually verify: homepage → Scouting Report → Card Report → back → browser back
5. Submit test feedback and confirm admin retrieval path
6. Confirm Supabase migration `20260711_beta_feedback.sql` is applied in staging

**Do not merge or deploy until verification pass is complete.**

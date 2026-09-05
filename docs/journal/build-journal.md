# Dev Journal — LossGuard

Single consolidated entry (built solo, full-time, over the submission
window) rather than separate daily files — logged here as the work
happened, in build order.

---

## Phase 1 — Research + framing

**Goal:** Decide what NOT to build, before building anything.  
**Did:** Competitive research (Riskified, Forter, Ravelin, Mastercard
Return Risk Intelligence) showed basic return-risk scoring and
device/address fraud-ring graphs are already commoditized. Pivoted from a
generic "return fraud detector" to an expected-loss-prioritization engine,
grounded in cost-sensitive fraud-detection research. Locked dataset schema
and feature list (behavioral vs structural split).  
**Output:** `docs/research-notes.md`, `docs/dataset-schema.md`.

## Phase 2 — Backend foundation + synthetic data

**Goal:** DB, models, synthetic dataset generator.  
**Did:** Built SQLAlchemy schema (users/orders/returns/links), Faker-based
seed script with NRF-sourced distributions (19-20% base return rate,
apparel 25-40%, 9% fraud share of returns).  
**What broke:** First EDA pass showed fraud-ring and genuine return rates
barely overlapping (means 0.43 vs 0.21) — too easy to separate by
behavior alone, undermining the core thesis. Tuned fraud-ring return
probability down (30-45% → 20-35%) to force real overlap with genuine
apparel buyers.

## Phase 3 — ML baseline, and the first real bug

**Goal:** Behavioral-only baseline model (Logistic Regression, XGBoost).  
**What broke:** Initial results were suspiciously perfect — 100% recall,
98.9% AUC — using ONLY behavioral features, which shouldn't be possible
given the thesis. Diagnosed with a per-feature separation-ratio script
(`diagnose_leakage.py`): `category_return_concentration` had a 5.63
separation ratio (vs 0.1-0.7 for every other feature), because the
fraud-ring generator force-assigned every ring member's orders to a single
category — an artifact of the data generator, not a real fraud signal.  
**Fix:** Mixed 1-3 orders from other categories into each ring member's
order history. Re-ran: XGBoost dropped to a realistic 63% precision, 93%
AUC — the first genuinely usable baseline.

## Phase 4 — Graph engine, and a second leakage bug

**Goal:** NetworkX shared-resource graph, cluster features, combined model.  
**Did:** Built bipartite user↔resource graph → projected to user-user
graph → connected components as clusters. Correctly detected all 15
seeded fraud rings on first run.  
**What broke:** Combined model hit 100% precision/recall/AUC again.
Feature importances showed `cluster_size` at 93% — because genuine users
had ZERO organic device/address sharing, making "in any cluster" a
tautological fraud proxy, not a learned pattern.  
**Fix:** Added ~15% organic sharing among genuine users (family/roommate
pattern), and softened fraud-ring internal sharing rates (0.8/0.6/0.5 →
0.65/0.5/0.4) so cluster size ranges overlap between genuine and fraud
populations. Final result: 85.3% recall, 100% precision (caveated in
decisions.md given moderate test-set size), `cluster_size` importance
reduced to 56% with 5+ other features meaningfully contributing.

## Phase 5 — Decision engine (hero feature) + backend API

**Goal:** Expected Loss formula, tiered decisions, full FastAPI wiring.  
**Did:** Implemented `Expected Loss = risk_score × refund_amount` with
bounded tiering (auto_approve / verify / manual_review) — deliberately
simple/hardcoded rather than a second ML model, for auditability (see
`decisions.md`). Wired ML + graph + decision engine into `case_service.py`
and exposed via FastAPI (`/cases`, `/case/{id}`, `/decision/{id}`,
`/stats`, `/explain/{id}`).  
**What broke:** `/stats` was recomputing full evidence (ML + graph + DB
queries) for every one of 1,387 returns on every request, exhausting the
SQLAlchemy connection pool (`QueuePool limit... connection timed out`).  
**Fix:** Capped the sample used for dashboard aggregation (150 cases,
randomly sampled — not first-N, which had been silently excluding later-
inserted fraud-ring rows) and increased pool size as a safety margin.

## Phase 6 — Frontend + integration polish

**Goal:** Next.js dashboard, case detail page, end-to-end demo.  
**Did:** Landing page with animated expected-loss counter, command center
sorted by expected loss (not risk score), case detail page with animated
risk gauge, evidence panel, AI summary (deterministic template, not a live LLM
call — see decisions.md D1), and approve/verify/reject
actions logging to `DecisionLog`.  
**What broke:** `create-next-app` scaffold never fully completed early on
— `package.json` was missing `next`/`react`/scripts entirely, and several
config files (`tsconfig.json`, `tailwind.config.js`, `postcss.config.js`,
`app/layout.tsx`, `app/globals.css`) were absent, causing `npm run dev` to
fail with "Missing script: dev". Rebuilt the scaffold files manually.
Dashboard also initially showed 0 manual-review cases because the
case-sampling logic took the first N rows by insertion order, which
happened to be all genuine users (fraud rings inserted later in the seed
script).  
**Fix:** fixed by switching to random sampling.

---

## Overall reflection

The recurring pattern across every "what broke" moment was the same:
synthetic data is easy to accidentally make *too clean*, in ways that
silently produce impressive-looking but meaningless metrics. Catching this
required treating suspiciously perfect results as a bug signal, not a win
— and building a small diagnostic script (`diagnose_leakage.py`) early
enough to keep using it through every dataset iteration.
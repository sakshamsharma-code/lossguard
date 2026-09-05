# Architecture — LossGuard

## System flow

```
Orders / Returns / Device-Address-Payment Links (SQLite)
                    ↓
        Feature Engineering (behavioral — soft signals)
        return_rate_30d/90d, avg_order_value, time_since_signup,
        return_to_purchase_gap, category_return_concentration
                    ↓
        Graph Engine (NetworkX — structural/hard signals)
        shared device/address/payment → connected components →
        cluster_size, cluster_density, shared_*_count
                    ↓
        ML Risk Model (XGBoost)
        behavioral + structural features → risk_score (0-1)
                    ↓
        Decision Engine (hero feature)
        Expected Loss = risk_score × refund_amount
        → tiered action: auto_approve / verify / manual_review
                    ↓
        LLM Explanation Layer (stub — see decisions.md D1)
        structured evidence JSON → human-readable case summary
        (explanation only, never decision)
                    ↓
        FastAPI backend  →  Next.js dashboard (Command Center + Case Detail)
                    ↓
        Human reviewer decision logged (approve/verify/reject)
```

## Why this layering

**Behavioral features are computed first but weighted least.** They are
noisy and easy for a fraud ring to game (research-notes.md §5) — our
dataset is deliberately constructed so behavior alone can't cleanly
separate fraud from genuine users.

**The graph engine is the core differentiator.** It surfaces structural
relationships (shared device/address/payment) that a fraud ring cannot
easily fake, because faking them requires genuinely sharing resources.

**The ML model combines both**, but structural features carry meaningfully
more predictive weight in the trained model (see feature importances in
decisions.md / README results table).

**The decision engine is intentionally simple and hardcoded** — not
another ML model. This is a deliberate design choice: ML is used where
pattern complexity genuinely requires it (risk scoring), but the
downstream policy of "what happens given this risk and this exposure"
needs to be transparent, auditable, and defensible to a human reviewer.
A merchant should be able to explain in one sentence why a case was
routed to manual review — that would not be true if a second black-box
model made that call.

**The LLM sits outside this decision path entirely.** It receives the
final computed evidence and explains it in plain language; it has no
ability to change the risk score, the expected loss, or the decision
tier. See `decisions.md` §D1 for the full reasoning.

## Component responsibilities

| Module | Responsibility |
|---|---|
| `app/db/` | Schema, seeding (synthetic data), DB session management |
| `app/ml/` | Feature engineering, model training, live prediction |
| `app/graph/` | Shared-resource graph construction, cluster detection |
| `app/decision/` | Expected Loss calculation + bounded tiering logic |
| `app/explain/` | LLM case-explanation (isolated, read-only, no decision power) |
| `app/services/` | Composes DB + ML + graph + decision into one evidence bundle per case |
| `app/main.py` | FastAPI routes, wires the above together |
| `frontend/app/` | Command Center (case list) + Case Detail (evidence, gauge, actions) |

## Data flow for a single case (`GET /case/{return_id}`)

1. Fetch the return + its user from SQLite
2. Compute behavioral features from that user's order/return history
3. Look up the user's position in the shared-resource graph (cached
   in-process; see `case_service.py`)
4. Run the combined XGBoost model → `risk_score`
5. Run the decision engine → `expected_loss`, `decision_tier`
6. Return everything as one `CaseEvidence` object to the frontend
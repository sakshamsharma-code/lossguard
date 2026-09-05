# LossGuard — Expected-Loss-Aware Return-Fraud Intervention Engine

Razorpay AI Builder Internship 2026 — Track 02 (AI Risk Manager)

Most fraud tools ask "is this risky?" LossGuard asks a more useful
question: **how much money is genuinely at stake, and where should a
merchant's limited review capacity go first?**

It combines a behavioral + structural (shared-resource graph) ML risk
model with an Expected Loss (`risk_score x refund_amount`) prioritization
engine, so a high-value medium-risk case gets reviewed before a
low-value high-risk one. Every decision is bounded (auto-approve /
verify / manual_review) and routes to a human reviewer — the system
never autonomously blocks or bans an account.

---

## What's real vs simulated in this build

Being upfront about this because it materially affects how the project
should be read:

| Component | Status |
|---|---|
| ML risk model (XGBoost, behavioral + graph features) | **Real**, trained on the synthetic dataset in this repo |
| Graph engine (NetworkX, shared device/address/payment) | **Real** |
| Decision engine (Expected Loss + tiering) | **Real**, hardcoded/deterministic by design (see `docs/decisions.md` D1) |
| Case-explanation layer (`backend/app/explain/explain_service.py`) | **Deterministic template**, not a live LLM API call. The evidence schema and function signature are already shaped for a drop-in Gemini/Groq call — swapping the template body is a same-file change — but no external API is wired up in this submission. |
| Dataset | **Synthetic**, generated with Faker using NRF-sourced return-rate distributions — not real production data |
| Deployment | **Local only** — runs via `uvicorn` + `next dev`, no hosted/cloud URL |

See `docs/decisions.md` (D1) and `docs/architecture.md` for the full
reasoning behind each of these choices.

---

## Folder structure

```
lossguard/
├── README.md                     — this file
├── .gitignore
│
├── docs/                         — design reasoning & process (read these first)
│   ├── research-notes.md         — competitive research, why this framing was chosen,
│   │                                LLM placement rationale (§7)
│   ├── dataset-schema.md         — feature list (behavioral / structural / financial)
│   ├── architecture.md           — system flow diagram, component responsibilities,
│   │                                data flow for a single case
│   ├── decisions.md              — decision log (P1–P6): why LLM is explanation-only,
│   │                                why NetworkX not a TGNN, dataset-leakage fixes, etc.
│   └── journal/
│       └── build-journal.md      — day-by-day build log: what was done, what broke,
│                                    how it was fixed (Phase 1–6)
│
├── backend/                       — FastAPI service
│   ├── requirements.txt
│   ├── lossguard.db               — SQLite DB (gitignored in a fresh clone; regenerate
│   │                                 via init_db.py + seed_data.py)
│   ├── data/
│   │   ├── behavioral_features.csv   — generated feature cache (gitignored)
│   │   └── graph_features.csv        — generated feature cache (gitignored)
│   └── app/
│       ├── main.py                — FastAPI app, route definitions:
│       │                             GET  /            — health check
│       │                             GET  /cases        — case list (sorted by expected loss)
│       │                             GET  /case/{id}    — full evidence bundle for one case
│       │                             POST /decision/{id}— log a reviewer decision
│       │                             GET  /stats        — dashboard aggregate stats
│       │                             POST /explain/{id} — plain-language case summary
│       ├── db/
│       │   ├── models.py          — SQLAlchemy schema (users, orders, returns, links)
│       │   ├── database.py        — DB session management
│       │   ├── seed_data.py       — synthetic data generator (Faker, NRF distributions)
│       │   ├── init_db.py         — creates tables + runs the seeder
│       │   └── eda_check.py       — sanity-checks the generated dataset
│       ├── ml/
│       │   ├── features.py        — behavioral feature engineering
│       │   ├── train.py           — behavioral-only baseline model
│       │   ├── train_with_graph.py— combined behavioral+graph model (final model)
│       │   ├── predict.py         — live inference used by the API
│       │   ├── diagnose_leakage.py— per-feature separation-ratio diagnostic script
│       │   │                        (used to catch the 3 leakage bugs in decisions.md D4)
│       │   ├── logreg_model.joblib, xgb_model.joblib, xgb_full_model.joblib,
│       │   │   scaler.joblib      — trained model artifacts (gitignored; regenerate by
│       │   │                        re-running train.py / train_with_graph.py)
│       ├── graph/
│       │   └── ring_detector.py   — bipartite user↔resource graph, connected-component
│       │                            cluster detection
│       ├── decision/
│       │   └── decision_engine.py — Expected Loss calculation + bounded tiering logic
│       │                            (deliberately simple/hardcoded — see decisions.md D1)
│       ├── explain/
│       │   └── explain_service.py — case-explanation layer (template — see table above)
│       ├── models/
│       │   └── schemas.py         — Pydantic request/response models (CaseEvidence, etc.)
│       └── services/
│           └── case_service.py    — composes DB + ML + graph + decision into one
│                                     CaseEvidence bundle per case
│
└── frontend/                       — Next.js dashboard
    ├── package.json, tsconfig.json, tailwind.config.js, postcss.config.js, next.config.js
    └── app/
        ├── page.tsx                — landing page (animated expected-loss counter)
        ├── layout.tsx, globals.css
        ├── dashboard/page.tsx      — command center: case list sorted by expected loss
        └── case/[id]/page.tsx      — case detail: risk gauge, evidence panel,
                                       AI summary, approve/verify/reject actions
```

Note: all UI code lives directly inside the relevant `page.tsx` files —
there is no separate `frontend/components/` folder. That was a
time-crunch call, not an oversight (see `docs/journal/build-journal.md`,
Day 6).

---

## Setup

### Backend

```bash
cd backend
pip install -r requirements.txt
python -m app.db.init_db          # creates lossguard.db and seeds synthetic data
python -m app.ml.train_with_graph # trains the combined model, writes .joblib files
uvicorn app.main:app --reload
```

API runs at `http://localhost:8000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard runs at `http://localhost:3000`.

---

## Results (see `docs/decisions.md` D5 for full honesty notes)

| Model | Precision | Recall |
|---|---|---|
| Behavioral-only baseline | 72.2% | 76.5% |
| Behavioral + structural (graph) — final model | 100.0% | 85.3% |

Net cost of errors dropped ~26% (₹56,291 → ₹41,691) after adding the
graph layer. The precision=1.000 figure is caveated in `decisions.md`
(D5) as partly a function of a moderate held-out test-set size (~34
fraud cases) — not presented as a claim of a flawless model.

---

## Where to read next

- New to the project? Start with `docs/research-notes.md` (why this
  problem framing was chosen over a generic fraud scorer).
- Want the system design? `docs/architecture.md`.
- Want to know *why* a specific choice was made (LLM scope, dataset
  fixes, what was deliberately left out)? `docs/decisions.md`.
- Want the day-by-day build story, including what broke and how it was
  diagnosed and fixed? `docs/journal/build-journal.md`.

# Research Notes — Merchant Risk Decision Engine (Track 02: AI Risk Manager)

> Purpose of this doc: everything we researched before writing a single line of code —
> market landscape, academic grounding, industry numbers, and why our design choices
> are defensible. Written so it's easy to re-read later and explain to judges/panel.

---

## 1. What the track actually asks for (verbatim requirements)

Source: Razorpay "Prove It" — Track 02 page.

- **Problem statement:** "Stop the merchant losing money to fraud, returns and chargebacks."
- **Deliverable bar:** "Build a working detector, verifier or auto-responder for **one
  class of loss**, with **measured precision and recall on a held-out test set**."
- **Why now (their framing):** AI-enabled fraud is hitting Indian BFSI while returns and
  chargebacks quietly eat margin. They explicitly want "risk and ML minded builders" who
  see something others miss.
- **The bar (hard requirements):**
  1. **Honest metrics including false-positive cost** — not just precision/recall/accuracy.
  2. **Strictly defense-only** — "anything offense-capable is disqualified." No
     autonomous punitive action; system must not be reverse-engineerable to evade it.

**Takeaway:** We are being evaluated on judgment (why we built it this way), not just
on whether a classifier runs.

---

## 2. Competitive landscape — what already exists (so we don't rebuild it)

| Product | What it already does | Source |
|---|---|---|
| **Riskified** | Device + behavioral data, identity/linkage intelligence, anomaly detection, fraud-ring detection, is moving toward explainable/dynamic decisions | riskified.com, ir.riskified.com |
| **Forter** | Identity-based fraud prevention at checkout/returns | industry knowledge |
| **Ravelin** | Visual graph exposing purchase/return/chargeback relationships between accounts | ravelin.com |
| **Stripe** | Frames refund abuse as a *cross-system* problem — signals scattered across systems, needs layered controls | stripe.com/resources/refund-abuse |
| **Mastercard Return Risk Intelligence** (launched Apr 2026) | Uses AI on historical returns/refunds/disputes to generate return-fraud risk scores | mastercard.com/in |

**Conclusion:** Basic ML fraud scoring, device/address linkage, and fraud-ring graph
detection are all commoditized. A plain "dataset → XGBoost → risk score → dashboard"
project would not stand out — it directly duplicates existing commercial products.

**Also confirmed:** Riskified's own research flags a real tension — over-aggressive
abuse control ends up unnecessarily restricting genuine customers. This is a known,
unsolved-in-practice problem, which is where our angle comes in (see Section 4).

---

## 3. Academic grounding for our core idea

**Idea:** Don't just predict risk — prioritize by *expected monetary loss* under
limited review capacity.

- A KU Leuven research paper on fraud detection explicitly minimizes **expected losses
  given limited investigation capacity**, ranking transactions by review priority
  rather than by raw fraud probability alone.
- A separate paper on cost-sensitive fraud detection notes that **false negatives carry
  far higher direct economic loss than false positives**, yet most literature under-
  evaluates the financial consequences of model decisions — motivating cost-sensitive
  approaches that explicitly fold in expected monetary loss.

**Takeaway:** Our formula `Expected Loss = Risk × Financial Exposure` is not an
invented gimmick — it's aligned with an active, published line of fraud-detection
research (cost-sensitive / expected-loss modeling). This is the strongest, most
defensible part of our differentiation.

**Note on early/evolving ring detection:** dynamic/temporal graph analysis for
catching abuse rings *as they form* (before they're fully connected) is also a real,
active research direction — cutting-edge versions use Temporal Graph Neural Networks
(TGNNs). **Decision: too heavy for a solo 15-day build** (needs GPU + training
pipeline + tuning). We will approximate the same insight with a **snapshot-based
NetworkX graph** (build the graph at daily/weekly checkpoints and show cluster growth
over time) rather than a full TGNN. Same story, buildable scope.

---

## 4. Industry numbers — used to make the synthetic dataset realistic

Source: NRF (National Retail Federation) 2025 Retail Returns Landscape report (most
recent benchmark heading into 2026), cross-checked against Richpanel, Capital One
Shopping, ShipNetwork, MakeMyReceipt.

| Metric | Value | Source |
|---|---|---|
| Overall e-commerce return rate | **~19.3–20.5%** of online orders | NRF 2025 / Happy Returns |
| Apparel/fashion return rate | **20–40%** (some segments up to 50%) | NRF, multiple aggregators |
| Electronics return rate | **8–15%** | NRF, multiple aggregators |
| Beauty/cosmetics return rate | **4–12%** | NRF, multiple aggregators |
| Total US retail returns (2025) | **$849.9 billion** | NRF / Happy Returns |
| **Fraudulent share of all returns** | **9% of returns are fraudulent** | NRF / Happy Returns, Oct 2025 |
| Retailers using AI for return-fraud detection | **85%** | NRF / Happy Returns |
| Cost per return processed | **$10–$65/item** (shipping, labor, inspection, restocking) | ShipNetwork, industry aggregators |

**How this maps to our dataset design:**
- Total orders → **~19–20% get returned** (this is our base return-generation rate).
- Of those returns → **~9% are fraud-labeled** in our synthetic data (NRF-sourced,
  not an arbitrary guess).
- Net effect: roughly **1.5–2% of all orders** are fraud-linked — this lands inside
  our originally planned 1–5% class-imbalance range, but now the number is
  *sourced*, not assumed.
- **Deliberately include a high-return-rate *genuine* population** (e.g. apparel
  buyers at 25–40% return rate) alongside the fraud cluster. This is what lets us
  empirically demonstrate our thesis in Section 5 — that raw behavioral rate alone
  is a weak, noisy signal.

---

## 5. Core thesis (why structural signals > behavioral signals)

> Individual behavioral signals are noisy and easy to game. Structural/relational
> signals (shared device, shared address, shared payment method) are far more costly
> for a fraud ring to fake, because they require genuinely sharing physical/financial
> resources across accounts.

Supporting reasoning:
- A genuine customer can have an 80% return rate (e.g. buys multiple sizes, keeps
  what fits — well documented apparel behavior, see Section 4 numbers).
- A fraud ring member might keep individual behavior deliberately "quiet" (low
  return rate, spread-out timing) specifically to evade a behavior-only classifier —
  but they still can't avoid sharing devices/addresses/payment instruments with
  their own ring, because that's how the ring extracts value in the first place.
- This is why our feature set is split into **soft (behavioral)** vs **hard
  (structural)** signals, and why the decision engine weights structural evidence
  more heavily than behavioral score alone.

---

## 6. Why payment-method-linking is our most "on-brand" signal for Razorpay specifically

Device fingerprinting requires a dedicated service (e.g. FingerprintJS) that a generic
e-commerce site may not have. **Razorpay, however, is a payment company** — payment-
instrument-level linkage (card fingerprint, UPI ID, wallet ID) is data they
*already process* as part of their core business. Framing shared-payment-method as our
hero structural signal (not just shared device) makes the project more directly
relevant to Razorpay's actual data reality, not just a generic e-commerce assumption.

---

## 7. LLM placement — the "right tool, right place" argument

Explicitly required by the track's evaluation criteria: *"the right tool in the right
place, and where you chose not to use one."*

- ❌ **Not used for:** fraud/no-fraud decisions, risk scoring, or any money-moving action.
  LLMs are probabilistic and not auditable in the way a rule/threshold is — money
  decisions need to be deterministic and defensible.
- ✅ **Used for:** turning a structured evidence bundle (risk score, expected loss,
  shared-device count, linked-account count, return rate, evidence confidence) into a
  concise, human-readable case summary for a merchant reviewer.
- This directly satisfies the track's **"strictly defense-only"** bar too — the LLM
  narrates evidence, it never gates or executes a decision.

---

## 8. Novelty / buildability matrix (final)

| Idea | Already exists commercially? | Novelty | Buildability (15 days, solo) | Decision |
|---|---|---|---|---|
| Basic return risk scorer | Yes | Low | High | ❌ Baseline only, not the differentiator |
| Fraud-ring graph (static) | Yes | Low–Med | Med | ⚠️ Include, but keep lightweight (NetworkX, not GNN) |
| **Cost-aware / expected-loss prioritization** | Partial | **High** | High | 🟢 **Hero feature — most time/polish here** |
| Early/evolving ring formation (snapshot proxy) | Partial | High | Med | 🟢 Include if time allows, simplified (no TGNN) |
| Risk + evidence confidence → tiered intervention | Partial | High | High | 🟢 Core decision logic |
| Human-in-the-loop feedback loop | Rare | High | Med | 🟡 Stretch goal, only if core is done early |
| Customer-friction-vs-loss-prevented metric | Rare | High | Med | 🟡 Stretch goal |

---

## 9. What we are explicitly NOT doing (and why — for `decisions.md` cross-reference)

- **Not** building a Temporal Graph Neural Network — real research direction, but too
  heavy/risky for a solo 15-day build. Using snapshot-based NetworkX graphs instead.
- **Not** letting the LLM make or gate any decision — track's defense-only requirement
  + general good practice for auditable money decisions.
- **Not** implementing real device fingerprinting — will simulate a `device_id` field
  and document clearly that production would use a service like FingerprintJS.
- **Not** claiming fabricated/cherry-picked metrics — all precision/recall/F1/false-
  positive-cost numbers will come from our actual held-out test set once built.

---

## 10. Sources referenced in this document

- Razorpay "Prove It" — Track 02 page (screenshot, in-app)
- riskified.com/fraud/prevention-solutions
- ir.riskified.com — Riskified refund-abuse analysis / "Dynamic Returns" release
- ravelin.com/solutions/refund-abuse-prevention
- stripe.com/resources/more/refund-abuse
- mastercard.com/in/en/news-and-trends/stories/2026/return-risk-intelligence.html
- NRF & Happy Returns, *2025 Retail Returns Landscape* (Oct 2025) — via Richpanel,
  Capital One Shopping, ShipNetwork, MakeMyReceipt, Opensend, Eightx aggregation
- KU Leuven / cost-sensitive fraud detection literature (expected-loss minimization
  under limited investigation capacity)
- General cost-sensitive learning literature on false-negative vs false-positive
  economic asymmetry in fraud detection



"Our synthetic fraud-return share (14.2%) is somewhat higher than the NRF-reported 9% industry baseline, because we deliberately elevated fraud-ring behavioral return rates to overlap with genuine high-return categories (apparel) — this was necessary to demonstrate that behavior alone cannot separate fraud from genuine users, which is the core thesis this project tests."
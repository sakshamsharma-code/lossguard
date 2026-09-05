# Dataset Schema — Merchant Risk Decision Engine

Companion to `research-notes.md`. This is the concrete, build-ready schema.

---

## 1. Feature categories (matches our core thesis)

### 🟡 Behavioral (soft signals — noisy, individually unreliable)
| Feature | Type | Why |
|---|---|---|
| `return_rate_30d` | float | Recent return rate — weak alone |
| `return_rate_90d` | float | Longer window — separates genuine vs sudden spike |
| `avg_order_value` | float | High-value returners carry more risk |
| `time_since_signup` | int (days) | Fresh accounts are more suspicious (rings use new accounts) |
| `return_to_purchase_gap_days` | float | Very fast returns can be suspicious |
| `category_return_concentration` | float (0-1) | Returns concentrated in one category vs spread out |

### 🔴 Structural (hard signals — costly to fake, our core differentiator)
| Feature | Type | Why |
|---|---|---|
| `shared_device_count` | int | # accounts sharing this device |
| `shared_address_count` | int | # accounts sharing this shipping address |
| `shared_payment_method_count` | int | # accounts sharing this payment instrument — **hero signal for Razorpay context** |
| `cluster_size` | int | Size of the connected-component graph this user belongs to |
| `cluster_density` | float | How tightly connected the cluster is |
| `days_since_cluster_formed` | int | Recent cluster formation = more suspicious |

### 💰 Financial exposure (for expected-loss calculation)
| Feature | Type | Why |
|---|---|---|
| `order_value` | float | Rupee value of this specific order |
| `refund_amount` | float | Actual refund exposure for this return |
| `customer_lifetime_value` | float | High-LTV genuine customers should get less friction |

**Derived (hero calculation):**
```
expected_loss = risk_score * refund_amount
```

---

## 2. Database tables

**`users`**
```
user_id (PK), signup_date, device_id, address_id, payment_method_id, ltv_score
```

**`orders`**
```
order_id (PK), user_id (FK), order_date, order_value, category
```

**`returns`**
```
return_id (PK), order_id (FK), user_id (FK), return_date, refund_amount,
reason_code, is_fraud (label — synthetic data only, ground truth for training/eval)
```

**`device_address_payment_links`** (feeds the graph engine)
```
link_id (PK), user_id (FK), device_id, address_id, payment_method_id
```

---

## 3. Realistic distribution rules (sourced from research-notes.md §4)

| Rule | Value | Source basis |
|---|---|---|
| Base order return rate | ~19–20% of orders | NRF 2025 |
| Apparel category return rate (genuine users) | 25–40% | NRF category benchmarks |
| Electronics category return rate (genuine users) | 8–15% | NRF category benchmarks |
| Fraud share of all returns | ~9% | NRF / Happy Returns 2025 |
| Net fraud-linked orders (overall) | ~1.5–2% of total orders | derived from above |
| Fraud ring size | 3–8 linked users per ring | design choice, kept small & realistic |

**Critical rule for the thesis to be provable:** deliberately give some *genuine*
users (especially apparel buyers) a high return rate (25–40%+), so that behavioral
signal alone cannot cleanly separate fraud from genuine — this is what lets us later
show, with real numbers, that structural signals add discriminative power beyond
behavior alone.

**Fraud ring construction rule:** ring members should look individually
unremarkable on behavioral features (moderate return rate, spread-out timing) but
share device/address/payment identifiers — so the ring is only visible through the
graph layer, not the behavioral layer.

---

## 4. Known limitation to document (not hidden)

`device_id` is simulated for this project. In production this would come from a
fingerprinting service (e.g. FingerprintJS) integrated at checkout. This is stated
explicitly in the README/limitations section — not glossed over.

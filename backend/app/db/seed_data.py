"""
Synthetic data generator for LossGuard.

Populates: users, orders, returns, device_address_payment_links

Distribution rules are sourced from docs/dataset-schema.md / research-notes.md
(NRF 2025 Retail Returns Landscape):
  - Base order return rate: ~19-20%
  - Apparel genuine return rate: 25-40% (deliberately high, to prove our
    thesis that behavioral rate alone can't separate fraud from genuine)
  - Electronics genuine return rate: 8-15%
  - Beauty genuine return rate: 4-12%
  - Fraud share of all returns: ~9% -> net ~1.5-2% of all orders are
    fraud-linked

Fraud ring design rule: ring members look individually unremarkable on
behavior (moderate return rate, spread-out timing) but SHARE device_id /
address_id / payment_method_id with each other. This is what makes them
only detectable via the graph layer, not the behavioral layer alone.

Run with: python -m app.db.seed_data
"""

import random
import uuid
from datetime import date, timedelta

from faker import Faker

from app.db.database import SessionLocal, engine, Base
from app.db import models

fake = Faker()
random.seed(42)  # reproducible runs

# ---------------- Config ----------------

NUM_GENUINE_USERS = 800
NUM_FRAUD_RINGS = 15          # each ring = 3-8 linked users
FRAUD_RING_SIZE_RANGE = (3, 8)

CATEGORIES = ["apparel", "electronics", "beauty"]
CATEGORY_WEIGHTS = [0.5, 0.3, 0.2]  # apparel most common (highest return-rate category)

CATEGORY_RETURN_RATE = {
    "apparel": (0.25, 0.40),
    "electronics": (0.08, 0.15),
    "beauty": (0.04, 0.12),
}

ORDER_VALUE_RANGE = {
    "apparel": (500, 5000),
    "electronics": (2000, 60000),
    "beauty": (300, 3000),
}

TODAY = date(2026, 8, 24)
SIGNUP_WINDOW_DAYS = 365 * 2  # signups spread over last 2 years

ORDERS_PER_USER_RANGE = (2, 12)


# ---------------- Helpers ----------------

def random_date(days_back_max, days_back_min=0):
    days_back = random.randint(days_back_min, days_back_max)
    return TODAY - timedelta(days=days_back)


def new_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


# ---------------- Genuine users ----------------

def generate_genuine_user(shared_pool=None):
    """
    A genuine user usually has their OWN device/address/payment method.
    BUT: some genuine users organically share an identifier (family sharing
    a home address, roommates sharing a device, etc.) — this is realistic
    AND necessary: without any organic sharing among genuine users,
    cluster_size becomes a tautological proxy for the fraud label
    (cluster>1 always = fraud in the data), which would make the graph
    signal trivially "too easy" rather than a genuine structural insight.
    """
    signup = random_date(SIGNUP_WINDOW_DAYS)

    device_id = new_id("device")
    address_id = new_id("addr")
    payment_method_id = new_id("pay")

    # ~15% of genuine users organically share an identifier with 1-2 other
    # genuine users (family/roommate pattern). This keeps genuine cluster
    # sizes (up to 3) overlapping with the low end of fraud-ring sizes
    # (3-8), so cluster_size alone isn't a clean fraud/genuine separator —
    # forcing the model to actually use density/shared-count nuance rather
    # than just "is this user in ANY cluster".
    if shared_pool is not None and random.random() < 0.15 and len(shared_pool) > 0:
        partner_field, partner_value = random.choice(shared_pool)
        if partner_field == "address_id":
            address_id = partner_value
        elif partner_field == "device_id":
            device_id = partner_value

    user = models.User(
        user_id=new_id("user"),
        signup_date=signup,
        device_id=device_id,
        address_id=address_id,
        payment_method_id=payment_method_id,
        ltv_score=round(random.uniform(0, 100), 2),
    )

    if shared_pool is not None:
        # register this user's identifiers as potential future share-targets
        shared_pool.append(("address_id", address_id))
        shared_pool.append(("device_id", device_id))

    return user


def generate_orders_and_returns_for_user(user, db, force_category=None, category_sequence=None, is_fraud_ring=False):
    if category_sequence is not None:
        n_orders = len(category_sequence)
    else:
        n_orders = random.randint(*ORDERS_PER_USER_RANGE)
    orders_created = []

    for i in range(n_orders):
        if category_sequence is not None:
            category = category_sequence[i]
        else:
            category = force_category or random.choices(CATEGORIES, weights=CATEGORY_WEIGHTS)[0]
        low, high = ORDER_VALUE_RANGE[category]
        order_value = round(random.uniform(low, high), 2)

        order_date_ = random_date(SIGNUP_WINDOW_DAYS, 0)
        # order must be after signup
        if order_date_ < user.signup_date:
            order_date_ = user.signup_date + timedelta(days=random.randint(0, 30))
            if order_date_ > TODAY:
                order_date_ = TODAY

        order = models.Order(
            order_id=new_id("order"),
            user_id=user.user_id,
            order_date=order_date_,
            order_value=order_value,
            category=category,
        )
        db.add(order)
        orders_created.append((order, category))

    db.flush()  # get order_ids usable for FK before commit

    # Decide returns based on category return-rate (genuine) or elevated
    # rate (fraud ring), but keep fraud-ring individual behavior "quiet" —
    # moderate, not extreme — so it's NOT obviously flaggable by behavior
    # alone. This is core to the thesis in research-notes.md §5.
    for order, category in orders_created:
        if is_fraud_ring:
            # Deliberately overlaps with genuine apparel return-rate range
            # (25-40%) rather than sitting clearly above it — this is what
            # makes behavioral signal alone insufficient to separate fraud
            # from genuine, forcing the structural/graph layer to add real
            # value. See research-notes.md §5 for the reasoning.
            return_prob = random.uniform(0.20, 0.35)
        else:
            low, high = CATEGORY_RETURN_RATE[category]
            return_prob = random.uniform(low, high)

        if random.random() < return_prob:
            return_date_ = order.order_date + timedelta(days=random.randint(1, 30))
            if return_date_ > TODAY:
                return_date_ = TODAY

            refund_amount = round(order.order_value * random.uniform(0.8, 1.0), 2)

            ret = models.Return(
                return_id=new_id("ret"),
                order_id=order.order_id,
                user_id=user.user_id,
                return_date=return_date_,
                refund_amount=refund_amount,
                reason_code=random.choice(
                    ["size_issue", "not_as_described", "changed_mind",
                     "defective", "wrong_item", "no_longer_needed"]
                ),
                is_fraud=is_fraud_ring,  # ground truth label, synthetic only
            )
            db.add(ret)


# ---------------- Fraud rings ----------------

def generate_fraud_ring(db):
    """
    A ring of 3-8 users who SHARE device/address/payment identifiers.
    Individually their behavior looks moderate (not extreme), but the
    graph layer will expose the shared-resource pattern.
    """
    ring_size = random.randint(*FRAUD_RING_SIZE_RANGE)

    shared_device = new_id("device")
    shared_address = new_id("addr")
    shared_payment = new_id("pay")

    # Ring formation timing: MIX of recent and established rings.
    # If every ring were recent, account-age alone would trivially predict
    # fraud (an easy shortcut that would make our structural/graph layer
    # look unnecessary). Real fraud rings include both fresh rings AND
    # long-established ones — mixing both keeps time_since_signup an
    # unreliable behavioral signal on its own, and makes
    # days_since_cluster_formed meaningfully useful for the later
    # early-ring-detection feature.
    ring_formed_days_ago = random.randint(5, 400)
    ring_base_signup = TODAY - timedelta(days=ring_formed_days_ago)

    ring_users = []
    for i in range(ring_size):
        signup = ring_base_signup + timedelta(days=random.randint(0, 10))
        # Mix: some ring members share ALL identifiers, some share only 1-2
        # (more realistic — full overlap for every member is too clean/obvious).
        # Kept moderate (not too high) so structural signal isn't trivially
        # "any sharing = fraud" — density/count nuance should still matter.
        share_device = random.random() < 0.65
        share_address = random.random() < 0.5
        share_payment = random.random() < 0.4

        user = models.User(
            user_id=new_id("user"),
            signup_date=signup,
            device_id=shared_device if share_device else new_id("device"),
            address_id=shared_address if share_address else new_id("addr"),
            payment_method_id=shared_payment if share_payment else new_id("pay"),
            ltv_score=round(random.uniform(0, 30), 2),  # rings tend to be low-LTV
        )
        db.add(user)
        ring_users.append(user)

    db.flush()

    category = random.choice(CATEGORIES)
    other_categories = [c for c in CATEGORIES if c != category]
    for user in ring_users:
        # Ring targets one category predominantly (realistic — rings often
        # focus on a product type with resale value), but NOT exclusively.
        # 100% concentration was an artifact of force_category in earlier
        # version — that made category_return_concentration a near-perfect
        # giveaway feature (separation ratio 5.63 vs 0.1-0.68 for everything
        # else), which isn't a real fraud pattern, just a synthetic-data bug.
        user_orders_categories = [category] * random.randint(3, 6) + \
            random.choices(other_categories, k=random.randint(1, 3))
        random.shuffle(user_orders_categories)
        generate_orders_and_returns_for_user(
            user, db, category_sequence=user_orders_categories, is_fraud_ring=True
        )

    return ring_users


# ---------------- Link table population ----------------

def populate_links(db):
    """
    device_address_payment_links: one row per user capturing their
    device/address/payment identifiers, for the graph engine to consume.
    """
    users = db.query(models.User).all()
    for u in users:
        link = models.DeviceAddressPaymentLink(
            user_id=u.user_id,
            device_id=u.device_id,
            address_id=u.address_id,
            payment_method_id=u.payment_method_id,
        )
        db.add(link)


# ---------------- Main ----------------

def seed():
    Base.metadata.create_all(bind=engine)  # safety: ensure tables exist
    db = SessionLocal()

    try:
        print(f"Generating {NUM_GENUINE_USERS} genuine users...")
        shared_pool = []
        for _ in range(NUM_GENUINE_USERS):
            user = generate_genuine_user(shared_pool=shared_pool)
            db.add(user)
            db.flush()
            generate_orders_and_returns_for_user(user, db, is_fraud_ring=False)

        print(f"Generating {NUM_FRAUD_RINGS} fraud rings "
              f"({FRAUD_RING_SIZE_RANGE[0]}-{FRAUD_RING_SIZE_RANGE[1]} users each)...")
        total_fraud_users = 0
        for _ in range(NUM_FRAUD_RINGS):
            ring = generate_fraud_ring(db)
            total_fraud_users += len(ring)

        print("Populating device/address/payment link table...")
        populate_links(db)

        db.commit()

        n_users = db.query(models.User).count()
        n_orders = db.query(models.Order).count()
        n_returns = db.query(models.Return).count()
        n_fraud_returns = db.query(models.Return).filter(models.Return.is_fraud == True).count()

        print("\n✅ Seed complete.")
        print(f"   Users:          {n_users} (genuine: {NUM_GENUINE_USERS}, fraud-ring: {total_fraud_users})")
        print(f"   Orders:         {n_orders}")
        print(f"   Returns:        {n_returns}")
        print(f"   Fraud returns:  {n_fraud_returns} ({100 * n_fraud_returns / max(n_returns,1):.1f}% of returns)")
        print(f"   Overall return rate: {100 * n_returns / max(n_orders,1):.1f}% of orders")

    except Exception as e:
        db.rollback()
        print(f"❌ Error during seeding, rolled back: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
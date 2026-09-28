"""
generate_data.py
Generates synthetic auto/home insurance data for the Dashboard Agent project.

Run once to create the data files:
    python generate_data.py

Output:
    data/policies.csv   — 1,000 insurance policies
    data/quotes.csv     — ~2,700 quotes (bound + lost)
    data/claims.csv     — ~500 claims
"""

import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta
import os

# Reproducible results — same data every run
np.random.seed(42)
random.seed(42)

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
N_POLICIES       = 1000    # Number of bound policies
BIND_RATE        = 0.37    # 37% of all quotes convert → total quotes ≈ 2,703
DATE_START       = datetime(2023, 1, 1)
DATE_END         = datetime(2026, 8, 1)   # Latest policy effective date
CLAIM_RATE       = 0.48    # 48% of policies generate at least one claim
MULTI_CLAIM_RATE = 0.18    # Of those, 18% get a second claim
TODAY            = datetime(2026, 9, 28)  # Reference "today" for the dataset

# ── LOOKUP TABLES ─────────────────────────────────────────────────────────────
STATES = [
    'CA', 'TX', 'FL', 'NY', 'PA', 'IL', 'OH', 'GA', 'NC', 'MI',
    'NJ', 'VA', 'WA', 'AZ', 'MA', 'TN', 'IN', 'MO', 'MD', 'WI',
    'CO', 'MN', 'SC', 'AL', 'LA', 'KY', 'OR', 'OK', 'CT', 'UT',
]
# Weights based roughly on state population — CA and TX get the most quotes
_SW = np.array([
    12, 9, 7, 6, 4, 4, 3.5, 3.3, 3.3, 3.0,
     2.8, 2.7, 2.5, 2.3, 2.2, 2.1, 2.1, 1.9, 1.9, 1.8,
     1.8, 1.7, 1.6, 1.5, 1.4, 1.4, 1.3, 1.2, 1.1, 1.0,
])
STATE_PROBS = _SW / _SW.sum()

PRODUCTS      = ['auto', 'home']
PRODUCT_PROBS = [0.70, 0.30]   # 70% auto, 30% home

CHANNELS      = ['agent', 'direct', 'broker']
CHANNEL_PROBS = [0.45, 0.35, 0.20]

AUTO_CLAIM_TYPES = ['collision', 'comprehensive', 'liability', 'bodily_injury']
HOME_CLAIM_TYPES = ['fire', 'water_damage', 'theft', 'wind_damage']


# ── HELPERS ───────────────────────────────────────────────────────────────────

def random_date(start: datetime, end: datetime) -> datetime:
    return start + timedelta(days=random.randint(0, max(0, (end - start).days)))

def fmt(d: datetime) -> str:
    return d.strftime('%Y-%m-%d')


# ── 1. POLICIES ───────────────────────────────────────────────────────────────
print("Generating policies...")

policy_ids   = [f'POL{i:06d}' for i in range(1, N_POLICIES + 1)]
customer_ids = [f'CUS{i:06d}' for i in range(1, N_POLICIES + 1)]

states   = np.random.choice(STATES,    N_POLICIES, p=STATE_PROBS)
products = np.random.choice(PRODUCTS,  N_POLICIES, p=PRODUCT_PROBS)
channels = np.random.choice(CHANNELS,  N_POLICIES, p=CHANNEL_PROBS)

effective_dates = [random_date(DATE_START, DATE_END) for _ in range(N_POLICIES)]
expiry_dates    = [d + timedelta(days=365) for d in effective_dates]

# Annual premiums: auto $800–$2,500, home $1,200–$4,000
premiums = []
for prod in products:
    if prod == 'auto':
        p = float(np.random.normal(1_400, 300))
        premiums.append(round(max(800.0, min(p, 2_500.0)), 2))
    else:
        p = float(np.random.normal(2_200, 500))
        premiums.append(round(max(1_200.0, min(p, 4_000.0)), 2))

policies_df = pd.DataFrame({
    'policy_id':      policy_ids,
    'customer_id':    customer_ids,
    'state':          states,
    'product':        products,
    'channel':        channels,
    'effective_date': [fmt(d) for d in effective_dates],
    'expiry_date':    [fmt(d) for d in expiry_dates],
    'annual_premium': premiums,
})


# ── 2. QUOTES ─────────────────────────────────────────────────────────────────
print("Generating quotes...")

# One bound quote per policy (quote comes before the effective date)
bound_rows = []
for i in range(N_POLICIES):
    eff    = effective_dates[i]
    q_date = eff - timedelta(days=random.randint(1, 45))
    # Quoted premium is within ±8% of the final bound premium
    q_prem = round(premiums[i] * random.uniform(0.92, 1.08), 2)
    bound_rows.append({
        'quote_id':       f'QUO{(i + 1):06d}',
        'policy_id':      policy_ids[i],
        'customer_id':    customer_ids[i],
        'state':          states[i],
        'product':        products[i],
        'channel':        channels[i],
        'quote_date':     fmt(q_date),
        'quoted_premium': q_prem,
        'status':         'bound',
        'bind_date':      fmt(eff),
    })

# Lost / still-open quotes (no corresponding policy)
N_LOST = round(N_POLICIES / BIND_RATE) - N_POLICIES
lost_rows = []
lost_cust_start = N_POLICIES + 1

for j in range(N_LOST):
    state   = np.random.choice(STATES,    p=STATE_PROBS)
    product = np.random.choice(PRODUCTS,  p=PRODUCT_PROBS)
    channel = np.random.choice(CHANNELS,  p=CHANNEL_PROBS)
    q_date  = random_date(DATE_START, datetime(2026, 9, 1))

    if product == 'auto':
        q_prem = round(max(800.0, min(float(np.random.normal(1_400, 300)), 2_500.0)), 2)
    else:
        q_prem = round(max(1_200.0, min(float(np.random.normal(2_200, 500)), 4_000.0)), 2)

    status = np.random.choice(['quoted', 'lost'], p=[0.25, 0.75])

    lost_rows.append({
        'quote_id':       f'QUO{(N_POLICIES + j + 1):06d}',
        'policy_id':      '',   # No policy — this quote was not converted
        'customer_id':    f'CUS{(lost_cust_start + j):06d}',
        'state':          state,
        'product':        product,
        'channel':        channel,
        'quote_date':     fmt(q_date),
        'quoted_premium': q_prem,
        'status':         status,
        'bind_date':      '',
    })

# Shuffle so bound and lost quotes are mixed together (realistic)
quotes_df = (
    pd.DataFrame(bound_rows + lost_rows)
    .sample(frac=1, random_state=42)
    .reset_index(drop=True)
)


# ── 3. CLAIMS ─────────────────────────────────────────────────────────────────
print("Generating claims...")

claim_rows    = []
claim_counter = 1

for i in range(N_POLICIES):
    if random.random() > CLAIM_RATE:
        continue  # This policy has no claims

    eff    = effective_dates[i]
    expiry = expiry_dates[i]
    latest = min(expiry, TODAY)

    if eff + timedelta(days=30) >= latest:
        continue  # Policy too new to realistically have a claim yet

    n_claims = 2 if random.random() < MULTI_CLAIM_RATE else 1

    for _ in range(n_claims):
        claim_date = random_date(eff + timedelta(days=30), latest)

        if products[i] == 'auto':
            claim_type = random.choice(AUTO_CLAIM_TYPES)
            claim_amt  = round(random.uniform(500.0, 25_000.0), 2)
        else:
            claim_type = random.choice(HOME_CLAIM_TYPES)
            claim_amt  = round(random.uniform(1_000.0, 80_000.0), 2)

        # Claim status depends on age: old claims tend to be closed
        days_old = (TODAY - claim_date).days
        if days_old > 180:
            status_probs = [0.05, 0.80, 0.15]   # mostly closed
        elif days_old > 60:
            status_probs = [0.30, 0.55, 0.15]
        else:
            status_probs = [0.70, 0.20, 0.10]   # mostly open

        claim_status = np.random.choice(['open', 'closed', 'denied'], p=status_probs)

        claim_rows.append({
            'claim_id':     f'CLM{claim_counter:06d}',
            'policy_id':    policy_ids[i],
            'customer_id':  customer_ids[i],
            'state':        states[i],
            'product':      products[i],
            'claim_date':   fmt(claim_date),
            'claim_type':   claim_type,
            'claim_amount': claim_amt,
            'claim_status': claim_status,
        })
        claim_counter += 1

claims_df = pd.DataFrame(claim_rows)


# ── WRITE OUTPUT ──────────────────────────────────────────────────────────────
os.makedirs('data', exist_ok=True)
policies_df.to_csv('data/policies.csv', index=False)
quotes_df.to_csv('data/quotes.csv',     index=False)
claims_df.to_csv('data/claims.csv',     index=False)

n_bound = len(bound_rows)
n_total = len(quotes_df)
print(f"\n  policies.csv  — {len(policies_df):,} rows")
print(f"  quotes.csv    — {n_total:,} rows  (bind rate: {n_bound / n_total * 100:.1f}%)")
print(f"  claims.csv    — {len(claims_df):,} rows")
print(f"\n  Total rows: {len(policies_df) + n_total + len(claims_df):,}")
print("\nDone.")

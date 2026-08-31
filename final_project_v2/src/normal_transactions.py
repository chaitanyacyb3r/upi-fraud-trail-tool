"""
Generates "normal" background transactions -- the noise your fraud rings
need to hide inside.

CONCEPT NOTE:
A transaction is a directed edge: (sender, receiver, amount, timestamp).
We're not building the graph yet -- just a flat list of these edges, same
shape as what a bank's CSV export would give an investigator.

Timing realism matters here: we spread transactions across business hours
with some randomness, NOT because it looks nice, but because your
"rapid pass-through" heuristic later only means something if normal
transactions genuinely don't cluster the way fraud hops do.
"""

import random
import numpy as np
from datetime import datetime, timedelta
from config import (
    NORMAL_TXN_AMOUNT_MEDIAN,
    NORMAL_TXN_AMOUNT_SIGMA,
    NORMAL_TXN_PER_ACCOUNT_MIN,
    NORMAL_TXN_PER_ACCOUNT_MAX,
    SIMULATION_DAYS,
)

SIM_START = datetime(2026, 6, 1)


def _lognormal_amount():
    """
    Log-normal distribution: mostly small values, occasional large ones.
    This is the actual real-world shape of transaction amounts -- a plain
    'average' would hide this and make our data look fake (flat/uniform).
    mu is set so the MEDIAN of the distribution lands on the real Rs 1,293
    stat, not the mean (median is the right anchor for skewed distributions).
    """
    mu = np.log(NORMAL_TXN_AMOUNT_MEDIAN)
    amount = np.random.lognormal(mean=mu, sigma=NORMAL_TXN_AMOUNT_SIGMA)
    return round(max(amount, 10), 2)  # floor at Rs 10, avoid absurd near-zero values


def _random_business_hours_timestamp():
    day_offset = random.randint(0, SIMULATION_DAYS - 1)
    # Weight towards daytime hours (9am-9pm), like real payment activity
    hour = int(np.clip(np.random.normal(loc=14, scale=4), 0, 23))
    minute = random.randint(0, 59)
    return SIM_START + timedelta(days=day_offset, hours=hour, minutes=minute)


def _pick_counterparty(account, all_accounts, social_circle_size=8):
    """
    Real people don't transact with random strangers uniformly -- they have
    a repeated 'social circle' of counterparties (friends, family, regular
    shops). We simulate that by giving each account a fixed small pool of
    counterparties it transacts with repeatedly, plus occasional one-offs.
    """
    others = [a for a in all_accounts if a["account_id"] != account["account_id"]]
    if "circle" not in account:
        account["circle"] = random.sample(others, min(social_circle_size, len(others)))
    if random.random() < 0.8:  # 80% of the time, transact within the circle
        return random.choice(account["circle"])
    return random.choice(others)  # 20% of the time, a one-off counterparty


def generate_normal_transactions(accounts: list[dict]) -> list[dict]:
    """
    Generates noise transactions for normal + hard_negative accounts.
    Mule accounts get their transactions from fraud_transactions.py instead --
    keeping these generators separate is what makes the fraud storylines
    controllable and injectable into the noise, rather than accidentally
    blended together.
    """
    background_accounts = [a for a in accounts if a["role"] in ("normal", "hard_negative")]
    transactions = []
    txn_counter = 1

    for acc in background_accounts:
        n_txns = random.randint(NORMAL_TXN_PER_ACCOUNT_MIN, NORMAL_TXN_PER_ACCOUNT_MAX)

        for _ in range(n_txns):
            counterparty = _pick_counterparty(acc, background_accounts)
            # direction: 50/50 this account is sender or receiver, EXCEPT
            # hard-negative subtypes get their behavior skewed deliberately
            # (handled properly in hard_negatives.py -- this file stays generic)
            sender, receiver = (acc, counterparty) if random.random() < 0.5 else (counterparty, acc)

            transactions.append({
                "txn_id": f"TXN{txn_counter:07d}",
                "sender_account_id": sender["account_id"],
                "receiver_account_id": receiver["account_id"],
                "amount": _lognormal_amount(),
                "timestamp": _random_business_hours_timestamp(),
                "mode": random.choice(["UPI", "UPI", "UPI", "IMPS", "NEFT"]),  # UPI-weighted
                "category": "normal",
            })
            txn_counter += 1

    return transactions


if __name__ == "__main__":
    from accounts import generate_accounts
    accs = generate_accounts()
    txns = generate_normal_transactions(accs)
    print(f"Generated {len(txns)} normal transactions")
    for t in txns[:5]:
        print(t)

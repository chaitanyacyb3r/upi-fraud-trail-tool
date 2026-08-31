"""
Injects the actual fraud patterns your Step-4 heuristics are meant to catch.

CONCEPT NOTE:
Each storyline below is a small subgraph, deliberately shaped to match one
detection heuristic:

  1. rapid_pass_through : victim -> mule -> mule -> cashout, each hop within
     minutes/hours. This is a LAYERING chain where speed is the tell.

  2. fan_in_aggregation  : many small "victim-like" payments converge on one
     mule account (task-scam style), then one large withdrawal. This is the
     classic smurfing/fan-in pattern.

  3. fan_out_layering    : a mule receives one big victim payment and
     immediately splits it out to 2-3 further mules, who each cash out
     separately. Fan-out + layering combined.

We consume accounts from the "mule" pool (role == "mule") and assign them
ring roles here. The 50 mule accounts get split across several ring
instances of each storyline, so your dataset has multiple independent
rings to find, not just one.
"""

import random
from datetime import datetime, timedelta
from config import (
    FRAUD_VICTIM_LOSS_MIN, FRAUD_VICTIM_LOSS_MAX,
    FAN_IN_DEPOSIT_MIN, FAN_IN_DEPOSIT_MAX,
    FAN_IN_CONTRIBUTOR_COUNT_MIN, FAN_IN_CONTRIBUTOR_COUNT_MAX,
    FRAUD_HOP_DELAY_MIN_MINUTES, FRAUD_HOP_DELAY_MAX_MINUTES,
)

SIM_START = datetime(2026, 6, 1)


def _hop_delay():
    minutes = random.randint(FRAUD_HOP_DELAY_MIN_MINUTES, FRAUD_HOP_DELAY_MAX_MINUTES)
    return timedelta(minutes=minutes)


def _random_start_ts():
    day = random.randint(0, 55)
    hour = random.randint(9, 22)
    return SIM_START + timedelta(days=day, hours=hour, minutes=random.randint(0, 59))


def _mk_txn(tid, sender, receiver, amount, ts, mode="UPI", note=""):
    return {
        "txn_id": f"TXN{tid:07d}",
        "sender_account_id": sender["account_id"],
        "receiver_account_id": receiver["account_id"],
        "amount": round(amount, 2),
        "timestamp": ts,
        "mode": mode,
        "category": "fraud",
        "fraud_note": note,   # ground truth: exists ONLY in our synthetic data
    }


def generate_fraud_transactions(accounts, all_background_accounts, start_txn_id):
    mules = [a for a in accounts if a["role"] == "mule"]
    random.shuffle(mules)
    transactions = []
    ring_id = 1
    tid = start_txn_id
    idx = 0

    # ---- Storyline A: rapid pass-through layering chains ----
    # Each ring uses 3 mule accounts: victim(external/normal) -> hop1 -> hop2 -> cashout
    while idx + 3 <= len(mules) and len([m for m in mules if m.get("used")]) < len(mules) * 0.4:
        hop1, hop2, cashout = mules[idx], mules[idx + 1], mules[idx + 2]
        idx += 3
        victim = random.choice(all_background_accounts)
        loss = random.uniform(FRAUD_VICTIM_LOSS_MIN, FRAUD_VICTIM_LOSS_MAX)
        t0 = _random_start_ts()

        transactions.append(_mk_txn(tid, victim, hop1, loss, t0, note=f"ring{ring_id}:victim->hop1")); tid += 1
        t1 = t0 + _hop_delay()
        transactions.append(_mk_txn(tid, hop1, hop2, loss * random.uniform(0.9, 0.98), t1, note=f"ring{ring_id}:hop1->hop2")); tid += 1
        t2 = t1 + _hop_delay()
        transactions.append(_mk_txn(tid, hop2, cashout, loss * random.uniform(0.85, 0.95), t2, note=f"ring{ring_id}:hop2->cashout")); tid += 1

        for a in (hop1, hop2, cashout):
            a["used"] = True
        ring_id += 1

    # ---- Storyline B: fan-in aggregation (task-scam style) ----
    remaining = [m for m in mules if not m.get("used")]
    while remaining and len(remaining) >= 1:
        mule = remaining.pop(0)
        n_contributors = random.randint(FAN_IN_CONTRIBUTOR_COUNT_MIN, FAN_IN_CONTRIBUTOR_COUNT_MAX)
        contributors = random.sample(all_background_accounts, min(n_contributors, len(all_background_accounts)))
        window_start = _random_start_ts()
        total_in = 0
        for c in contributors:
            amt = random.uniform(FAN_IN_DEPOSIT_MIN, FAN_IN_DEPOSIT_MAX)
            ts = window_start + timedelta(minutes=random.randint(0, 240))  # all within ~4hr window
            transactions.append(_mk_txn(tid, c, mule, amt, ts, note=f"ring{ring_id}:fanin")); tid += 1
            total_in += amt
        # single large withdrawal shortly after the fan-in window closes
        payout_ts = window_start + timedelta(minutes=250) + _hop_delay()
        sink = random.choice(all_background_accounts)
        transactions.append(_mk_txn(tid, mule, sink, total_in * random.uniform(0.9, 0.97), payout_ts, note=f"ring{ring_id}:payout")); tid += 1
        mule["used"] = True
        ring_id += 1
        if len(remaining) < 3:
            break

    # ---- Storyline C: fan-out layering (one victim payment splits across mules) ----
    remaining = [m for m in mules if not m.get("used")]
    while len(remaining) >= 3:
        entry = remaining.pop(0)
        branch1 = remaining.pop(0)
        branch2 = remaining.pop(0)
        victim = random.choice(all_background_accounts)
        loss = random.uniform(FRAUD_VICTIM_LOSS_MIN, FRAUD_VICTIM_LOSS_MAX)
        t0 = _random_start_ts()
        transactions.append(_mk_txn(tid, victim, entry, loss, t0, note=f"ring{ring_id}:victim->entry")); tid += 1

        split_ratio = random.uniform(0.4, 0.6)
        t1 = t0 + _hop_delay()
        transactions.append(_mk_txn(tid, entry, branch1, loss * split_ratio, t1, note=f"ring{ring_id}:entry->branch1")); tid += 1
        t2 = t0 + _hop_delay()
        transactions.append(_mk_txn(tid, entry, branch2, loss * (0.95 - split_ratio), t2, note=f"ring{ring_id}:entry->branch2")); tid += 1

        for branch in (branch1, branch2):
            t3 = max(t1, t2) + _hop_delay()
            sink = random.choice(all_background_accounts)
            share = loss * split_ratio if branch is branch1 else loss * (0.95 - split_ratio)
            transactions.append(_mk_txn(tid, branch, sink, share * random.uniform(0.9, 0.98), t3, note=f"ring{ring_id}:cashout")); tid += 1

        ring_id += 1

    return transactions, ring_id - 1


if __name__ == "__main__":
    from accounts import generate_accounts
    accs = generate_accounts()
    background = [a for a in accs if a["role"] in ("normal", "hard_negative")]
    txns, n_rings = generate_fraud_transactions(accs, background, start_txn_id=200000)
    print(f"Generated {len(txns)} fraud transactions across {n_rings} rings")
    for t in txns[:6]:
        print(t)

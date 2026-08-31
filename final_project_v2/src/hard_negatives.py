"""
Generates transactions for "hard negative" accounts -- legitimate accounts
DELIBERATELY designed to trigger your fraud heuristics, so you can measure
false positives honestly instead of accidentally grading your own homework.

This is the single most important file for making your project defensible.
Without this, "100% detection on synthetic data" proves nothing (Challenge 3
from earlier: if you design the fraud pattern and the detector together,
of course they match).

Three subtypes, each a legitimate "twin" of a fraud pattern:

1. freelancer_fan_in   -> twin of the MULE fan-in pattern
   Many small incoming payments from different clients, one larger
   outgoing payment (rent/savings transfer). Structurally similar to a
   mule collecting scam payments, but the counterparties are STABLE
   (same clients recur over time) and timing is NOT rapid pass-through.

2. family_bill_split   -> twin of the RAPID PASS-THROUGH pattern
   One person pays a big bill (rent/electricity), then quickly gets
   reimbursed by 2-3 family members. Fast in/out timing, but low amounts,
   tight social circle, recurring monthly pattern.

3. small_merchant       -> twin of the LAYERING pattern
   Receives many customer payments, pays multiple suppliers -- looks like
   a multi-hop chain, but is a stable, repeating business relationship,
   not a one-off obfuscation chain.
"""

import random
from datetime import timedelta
from config import FAN_IN_DEPOSIT_MIN, FAN_IN_DEPOSIT_MAX


def generate_hard_negative_transactions(accounts: list[dict], start_txn_id: int) -> list[dict]:
    hard_negatives = [a for a in accounts if a["role"] == "hard_negative"]
    all_others = [a for a in accounts if a["role"] != "mule"]  # negatives interact with normal world, not mules
    transactions = []
    tid = start_txn_id

    for acc in hard_negatives:
        if acc["subtype"] == "freelancer_fan_in":
            # Stable set of 6-10 "clients" who pay repeatedly over the 2 months
            clients = random.sample(all_others, random.randint(6, 10))
            for client in clients:
                # each client pays 2-4 times (recurring relationship, NOT one-off)
                for _ in range(random.randint(2, 4)):
                    day_offset = random.randint(0, 59)
                    transactions.append({
                        "txn_id": f"TXN{tid:07d}", "sender_account_id": client["account_id"],
                        "receiver_account_id": acc["account_id"],
                        "amount": round(random.uniform(2000, 15000), 2),
                        "timestamp": _ts(day_offset, spread_hours=True),
                        "mode": "UPI", "category": "hard_negative",
                    })
                    tid += 1
            # One monthly outgoing transfer (e.g. to savings) -- NOT within
            # minutes of any single incoming payment, so rapid-pass-through
            # heuristic should NOT fire even though fan-in heuristic might.
            for month in (20, 50):
                transactions.append({
                    "txn_id": f"TXN{tid:07d}", "sender_account_id": acc["account_id"],
                    "receiver_account_id": random.choice(all_others)["account_id"],
                    "amount": round(random.uniform(15000, 40000), 2),
                    "timestamp": _ts(month), "mode": "IMPS", "category": "hard_negative",
                })
                tid += 1

        elif acc["subtype"] == "family_bill_split":
            family = random.sample(all_others, random.randint(2, 3))
            # Monthly recurring: acc pays a big bill, family reimburses within hours
            for month_day in (5, 35, 55):
                bill_amount = round(random.uniform(3000, 8000), 2)
                bill_ts = _ts(month_day)
                transactions.append({
                    "txn_id": f"TXN{tid:07d}", "sender_account_id": acc["account_id"],
                    "receiver_account_id": random.choice(all_others)["account_id"],  # the biller
                    "amount": bill_amount, "timestamp": bill_ts,
                    "mode": "UPI", "category": "hard_negative",
                })
                tid += 1
                share = round(bill_amount / (len(family) + 1), 2)
                for member in family:
                    # reimbursement within 1-4 hours -- deliberately looks like
                    # rapid pass-through timing, but amounts are small and the
                    # same family members recur every month (stable circle)
                    reimburse_ts = bill_ts + timedelta(hours=random.uniform(0.5, 4))
                    transactions.append({
                        "txn_id": f"TXN{tid:07d}", "sender_account_id": member["account_id"],
                        "receiver_account_id": acc["account_id"],
                        "amount": share, "timestamp": reimburse_ts,
                        "mode": "UPI", "category": "hard_negative",
                    })
                    tid += 1

        elif acc["subtype"] == "small_merchant":
            customers = random.sample(all_others, random.randint(15, 25))
            suppliers = random.sample(all_others, random.randint(3, 5))
            # many small customer payments in, spread across the whole window
            for cust in customers:
                for _ in range(random.randint(1, 3)):
                    transactions.append({
                        "txn_id": f"TXN{tid:07d}", "sender_account_id": cust["account_id"],
                        "receiver_account_id": acc["account_id"],
                        "amount": round(random.uniform(200, 3000), 2),
                        "timestamp": _ts(random.randint(0, 59), spread_hours=True),
                        "mode": "UPI", "category": "hard_negative",
                    })
                    tid += 1
            # periodic supplier payouts -- NOT immediately after any single
            # customer payment, spread out like real business cash flow
            for supplier in suppliers:
                transactions.append({
                    "txn_id": f"TXN{tid:07d}", "sender_account_id": acc["account_id"],
                    "receiver_account_id": supplier["account_id"],
                    "amount": round(random.uniform(5000, 20000), 2),
                    "timestamp": _ts(random.randint(0, 59)),
                    "mode": "IMPS", "category": "hard_negative",
                })
                tid += 1

    return transactions


def _ts(day_offset, spread_hours=False):
    from datetime import datetime
    base = datetime(2026, 6, 1) + timedelta(days=day_offset)
    hour = random.randint(9, 21) if spread_hours else random.choice([10, 14, 18])
    minute = random.randint(0, 59)
    return base.replace(hour=hour, minute=minute)


if __name__ == "__main__":
    from accounts import generate_accounts
    accs = generate_accounts()
    txns = generate_hard_negative_transactions(accs, start_txn_id=90000)
    print(f"Generated {len(txns)} hard-negative transactions")
    for t in txns[:5]:
        print(t)

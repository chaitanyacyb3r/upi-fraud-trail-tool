"""
Generates the account population.

CONCEPT NOTE (so you can audit this, not just run it):
An "account" here is just a dictionary of metadata -- it is NOT a graph node
yet. The graph only gets built in Step 3, from the transactions these
accounts make. Right now we're only creating the "cast of characters."

We create three groups, each with a `role` label. The role is our ground
truth -- it lets us later check "did the heuristic correctly flag the fraud
accounts, and correctly leave the hard-negative accounts alone?" This label
is something a real investigator would NEVER have -- it only exists in our
synthetic data so WE can grade our own detector.
"""

import random
from faker import Faker
from config import (
    NUM_NORMAL_ACCOUNTS,
    NUM_HARD_NEGATIVE_ACCOUNTS,
    NUM_FRAUD_RING_ACCOUNTS,
    BANK_CODES_FOR_MASKED_ACCOUNTS,
)

fake = Faker("en_IN")  # Indian locale -> realistic names/addresses


def _make_account_number():
    # Indian account numbers vary in length by bank; 11-16 digits is realistic.
    length = random.choice([11, 12, 14, 16])
    return "".join(str(random.randint(0, 9)) for _ in range(length))


def _make_vpa(name_hint):
    # Realistic VPA handles seen in real exports: name@bank, phone@app
    handle_style = random.choice(["name", "phone"])
    domain = random.choice(["ybl", "okhdfcbank", "oksbi", "okicici", "okaxis", "paytm"])
    if handle_style == "name":
        base = name_hint.lower().replace(" ", ".")
        return f"{base}{random.randint(1,999)}@{domain}"
    else:
        return f"{fake.msisdn()[-10:]}@{domain}"


def _make_account(role: str, account_id: int) -> dict:
    name = fake.name()
    return {
        "account_id": f"ACC{account_id:05d}",
        "account_holder_name": name,
        "account_number": _make_account_number(),
        "bank": random.choice(BANK_CODES_FOR_MASKED_ACCOUNTS),
        "vpa": _make_vpa(name),
        "role": role,  # ground-truth label: normal / hard_negative / mule
        # subtype tells the transaction generator WHICH behavior pattern to give this account
        "subtype": None,
    }


def generate_accounts() -> list[dict]:
    accounts = []
    aid = 1

    # --- Normal population ---
    for _ in range(NUM_NORMAL_ACCOUNTS):
        acc = _make_account("normal", aid)
        acc["subtype"] = random.choice(
            ["salaried", "student", "small_shop_customer", "general"]
        )
        accounts.append(acc)
        aid += 1

    # --- Hard negatives: legitimate accounts that LOOK suspicious ---
    # These exist specifically to stress-test false positives later (Step 4).
    hard_negative_subtypes = ["freelancer_fan_in", "family_bill_split", "small_merchant"]
    for i in range(NUM_HARD_NEGATIVE_ACCOUNTS):
        acc = _make_account("hard_negative", aid)
        acc["subtype"] = hard_negative_subtypes[i % len(hard_negative_subtypes)]
        accounts.append(acc)
        aid += 1

    # --- Fraud ring accounts ---
    # Distributed into ring "roles": victim, mule_hop1, mule_hop2, cashout
    for _ in range(NUM_FRAUD_RING_ACCOUNTS):
        acc = _make_account("mule", aid)
        accounts.append(acc)
        aid += 1

    return accounts


if __name__ == "__main__":
    accs = generate_accounts()
    print(f"Generated {len(accs)} accounts")
    print("Sample:")
    for a in accs[:3]:
        print(a)
    for a in accs[NUM_NORMAL_ACCOUNTS:NUM_NORMAL_ACCOUNTS + 2]:
        print(a)

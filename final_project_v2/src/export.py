"""
Merges all transaction sources and exports in the REAL PhonePe CSV format
you confirmed from your own downloaded statement:

    Date, Time, Transaction Details, Transaction ID, UTR,
    Transaction Type, Credit/Debit Instrument, Amount

CONCEPT NOTE:
This is where we deliberately make the data "messy" the way real exports
are messy -- the counterparty info goes into a free-text "Transaction
Details" field (like "Paid by XXXXXX0729"), NOT a clean column. This is
what will make your Step-2 ingestion/parsing module necessary and
non-trivial, matching the real challenge we researched.

We write ONE CSV per account (matching reality: each statement you get
from a Section 94 BNSS disclosure is for ONE account), because that's
how an investigator actually receives and feeds data into your tool,
hop by hop (Step 5 of the real workflow we mapped out earlier).

We ALSO write a separate ground_truth.csv that is NEVER an input to your
ingestion/detection pipeline -- it's your answer key, used only in Step 4
to measure whether your heuristics actually work.
"""

import csv
import os
import random
from datetime import datetime


def _mask_account_number(acc_number: str) -> str:
    return "X" * (len(acc_number) - 4) + acc_number[-4:]


def _make_narration(counterparty_account: dict, direction: str, utr: str) -> str:
    """
    Builds a messy, realistic narration string like real PhonePe exports:
    'Paid to <Name>' / 'Received from <Name>' + masked account/VPA info,
    mimicking the structure you confirmed from your own statement.
    """
    masked = _mask_account_number(counterparty_account["account_number"])
    if direction == "debit":
        return (f"Paid to {counterparty_account['account_holder_name']}\n"
                f"UTR No. {utr}\nPaid by {masked}")
    else:
        return (f"Received from {counterparty_account['account_holder_name']}\n"
                f"UTR No. {utr}\nCredited to {masked}")


def _fake_utr():
    return "".join(str(random.randint(0, 9)) for _ in range(12))


def export_per_account_csvs(transactions, accounts, out_dir):
    """
    Writes one CSV per account, formatted like a real PhonePe statement
    export. This is the format Step-2 (ingestion) will parse.
    """
    os.makedirs(out_dir, exist_ok=True)
    accounts_by_id = {a["account_id"]: a for a in accounts}

    # Build a lookup: account_id -> list of (txn, direction)
    per_account = {a["account_id"]: [] for a in accounts}
    for t in transactions:
        s_id, r_id = t["sender_account_id"], t["receiver_account_id"]
        utr = _fake_utr()
        if s_id in per_account:
            per_account[s_id].append((t, "debit", utr))
        if r_id in per_account:
            per_account[r_id].append((t, "credit", utr))

    files_written = 0
    for acc_id, entries in per_account.items():
        if not entries:
            continue
        entries.sort(key=lambda e: e[0]["timestamp"])
        acc = accounts_by_id[acc_id]
        path = os.path.join(out_dir, f"{acc_id}_{acc['bank']}_statement.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "Time", "Transaction Details", "Transaction ID",
                              "UTR", "Transaction Type", "Credit/Debit Instrument", "Amount"])
            for t, direction, utr in entries:
                other_id = t["receiver_account_id"] if direction == "debit" else t["sender_account_id"]
                other = accounts_by_id.get(other_id)
                if other is None:
                    continue
                ts: datetime = t["timestamp"]
                narration = _make_narration(other, direction, utr)
                txn_type = "Debit" if direction == "debit" else "Credit"
                writer.writerow([
                    ts.strftime("%b %d, %Y"), ts.strftime("%I:%M %p"),
                    narration, t["txn_id"], utr, txn_type, t["mode"], f"{t['amount']:.2f}",
                ])
        files_written += 1
    return files_written


def export_ground_truth(transactions, accounts, out_path):
    """
    The answer key -- role/subtype per account and fraud-ring membership
    per transaction. This file is used ONLY for evaluating detection
    heuristics in Step 4. It must NEVER be fed into the ingestion pipeline,
    since a real investigator would never have this.
    """
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["account_id", "role", "subtype"])
        for a in accounts:
            writer.writerow([a["account_id"], a["role"], a.get("subtype") or ""])

    txn_out_path = out_path.replace(".csv", "_transactions.csv")
    with open(txn_out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["txn_id", "category", "fraud_note",
                         "sender_account_id", "receiver_account_id"])
        for t in transactions:
            writer.writerow([t["txn_id"], t["category"],
                             t.get("fraud_note", ""),
                             t.get("sender_account_id", ""),
                             t.get("receiver_account_id", "")])


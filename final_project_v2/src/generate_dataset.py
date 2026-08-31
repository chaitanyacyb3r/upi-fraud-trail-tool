"""
Main entry point: runs the full synthetic dataset generation pipeline.

Run with: python3 generate_dataset.py
"""

import random
import numpy as np
from faker import Faker

from accounts import generate_accounts
from normal_transactions import generate_normal_transactions
from hard_negatives import generate_hard_negative_transactions
from fraud_storylines import generate_fraud_transactions
from export import export_per_account_csvs, export_ground_truth
from export_account_mapping import export_account_mapping

SEED = 42  # fixed seed -> every full run produces the exact same dataset,
           # so account_mapping.csv always matches the statement CSVs.


def main():
    random.seed(SEED)
    np.random.seed(SEED)
    Faker.seed(SEED)

    print("Step 1: generating accounts...")
    accounts = generate_accounts()

    print("Step 1b: exporting account_id -> name mapping (same run, same objects)...")
    export_account_mapping(accounts, "../data/account_mapping.csv")
    print(f"  -> {len(accounts)} accounts")

    print("Step 2: generating normal background transactions...")
    normal_txns = generate_normal_transactions(accounts)
    print(f"  -> {len(normal_txns)} normal transactions")

    print("Step 3: generating hard-negative transactions...")
    hn_txns = generate_hard_negative_transactions(accounts, start_txn_id=100000)
    print(f"  -> {len(hn_txns)} hard-negative transactions")

    print("Step 4: injecting fraud storylines...")
    background_accounts = [a for a in accounts if a["role"] in ("normal", "hard_negative")]
    fraud_txns, n_rings = generate_fraud_transactions(accounts, background_accounts, start_txn_id=200000)
    print(f"  -> {len(fraud_txns)} fraud transactions across {n_rings} rings")

    all_txns = normal_txns + hn_txns + fraud_txns
    print(f"\nTotal transactions: {len(all_txns)}")

    print("\nStep 5: exporting per-account PhonePe-style CSV statements...")
    n_files = export_per_account_csvs(all_txns, accounts, out_dir="../data/statements")
    print(f"  -> {n_files} statement files written to ../data/statements/")

    print("Step 6: exporting ground truth (answer key, not for ingestion)...")
    export_ground_truth(all_txns, accounts, out_path="../data/ground_truth.csv")
    print("  -> ../data/ground_truth.csv and ../data/ground_truth_transactions.csv written")

    print("\nDone.")


if __name__ == "__main__":
    main()

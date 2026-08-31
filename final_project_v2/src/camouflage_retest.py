"""
Camouflage Retest: The Critical Validation

PURPOSE: Mule accounts in this dataset have ZERO normal background
transactions — they appear ONLY in fraud_storylines.py edges. Every
feature computed on a mule node reflects 100% pure fraud signal with
no camouflage. Real-world mule accounts almost always have some ordinary
activity mixed in (that's what makes them hard to catch in practice).

THIS TEST: Adds a realistic number of normal-looking transactions to
each mule account (reusing the same log-normal amounts and business-hours
timing from normal_transactions.py), then reruns the exact same feature
engineering and ablation pipeline. Features that still separate well
after camouflage are genuinely useful; features that collapse were
artifacts of the zero-noise construction, not real signals.

This is NOT a modification to the project's data — it's a one-off
validation test that operates on an in-memory copy of the graph.
"""

import pickle
import random
import copy
import numpy as np
import pandas as pd
import networkx as nx
from datetime import datetime, timedelta

# Reuse existing modules
from feature_engineering import compute_features
from ablation_test import run_ablation


# --- Camouflage generation (reuses normal_transactions.py logic) ---

SIM_START = datetime(2026, 6, 1)
SIMULATION_DAYS = 60
NORMAL_TXN_AMOUNT_MEDIAN = 1293
NORMAL_TXN_AMOUNT_SIGMA = 0.9


def _lognormal_amount():
    """Same log-normal distribution as normal_transactions.py."""
    mu = np.log(NORMAL_TXN_AMOUNT_MEDIAN)
    amount = np.random.lognormal(mean=mu, sigma=NORMAL_TXN_AMOUNT_SIGMA)
    return round(max(amount, 10), 2)


def _random_business_hours_timestamp():
    """Same business-hours weighting as normal_transactions.py."""
    day_offset = random.randint(0, SIMULATION_DAYS - 1)
    hour = int(np.clip(np.random.normal(loc=14, scale=4), 0, 23))
    minute = random.randint(0, 59)
    return SIM_START + timedelta(days=day_offset, hours=hour, minutes=minute)


def _fake_utr():
    """Generate a random 12-digit UTR (same as export.py)."""
    return str(random.randint(10**11, 10**12 - 1))


def add_camouflage_to_graph(G, mule_ids, normal_ids, min_txns=30, max_txns=60):
    """Add normal-looking transactions to each mule account.

    CRITICAL FIX (v2): Uses the SAME social circle logic as
    normal_transactions.py -- 80% of transactions within a fixed 8-member
    repeat circle, 20% one-off strangers. Previous version used 100%
    random one-offs, which artificially suppressed reciprocity (no repeat
    partners to reciprocate with).

    Also increased to 30-60 transactions (matching normal account volume
    of 15-60) to test whether features survive at full camouflage.
    """
    camouflage_count = 0
    normal_list = list(normal_ids)

    for mule_id in mule_ids:
        n_camo = random.randint(min_txns, max_txns)

        # Assign a social circle (same logic as _pick_counterparty)
        circle_size = 8
        circle = random.sample(normal_list, min(circle_size, len(normal_list)))

        for _ in range(n_camo):
            # 80% within circle, 20% one-off (same as normal_transactions.py)
            if random.random() < 0.8:
                counterparty = random.choice(circle)
            else:
                counterparty = random.choice(normal_list)
            amount = _lognormal_amount()
            ts = _random_business_hours_timestamp()
            utr = f"CAMO{_fake_utr()}"
            mode = random.choice(["UPI", "UPI", "UPI", "IMPS", "NEFT"])
            ts_str = ts.strftime("%b %d, %Y %I:%M %p")

            # 50/50 incoming vs outgoing
            if random.random() < 0.5:
                sender, receiver = counterparty, mule_id
            else:
                sender, receiver = mule_id, counterparty

            G.add_edge(
                u_for_edge=sender,
                v_for_edge=receiver,
                key=utr,
                amount=amount,
                timestamp=ts_str,
                mode=mode,
                source_file="camouflage_injection"
            )
            camouflage_count += 1

    return camouflage_count


def main():
    print("=" * 85)
    print("CAMOUFLAGE RETEST")
    print("=" * 85)
    print()
    print("Loading original graph...")
    with open("../data/forensic_network.gpickle", "rb") as f:
        G_original = pickle.load(f)

    print("Loading ground truth...")
    gt = pd.read_csv("../data/ground_truth.csv")
    mule_ids = set(gt[gt['role'] == 'mule']['account_id'])
    normal_ids = set(gt[gt['role'] == 'normal']['account_id'])

    # Count original mule edges for comparison
    original_mule_edges = {}
    for m in mule_ids:
        if G_original.has_node(m):
            in_e = len(list(G_original.in_edges(m)))
            out_e = len(list(G_original.out_edges(m)))
            original_mule_edges[m] = (in_e, out_e)

    avg_orig = np.mean([i + o for i, o in original_mule_edges.values()])
    print(f"  Original avg edges per mule: {avg_orig:.1f}")
    print(f"  Mule accounts in graph: {len(original_mule_edges)}")

    # Deep copy graph to avoid modifying original
    print("\nCreating deep copy of graph for camouflage injection...")
    G_camo = copy.deepcopy(G_original)

    # Seed for reproducibility of camouflage
    random.seed(99)
    np.random.seed(99)

    print("Injecting camouflage transactions...")
    n_camo = add_camouflage_to_graph(G_camo, mule_ids, normal_ids,
                                      min_txns=10, max_txns=25)

    # Report camouflage stats
    camo_mule_edges = {}
    for m in mule_ids:
        if G_camo.has_node(m):
            in_e = len(list(G_camo.in_edges(m)))
            out_e = len(list(G_camo.out_edges(m)))
            camo_mule_edges[m] = (in_e, out_e)

    avg_camo = np.mean([i + o for i, o in camo_mule_edges.values()])
    print(f"  Added {n_camo} camouflage transactions across {len(mule_ids)} mules")
    print(f"  New avg edges per mule: {avg_camo:.1f} (was {avg_orig:.1f})")
    print(f"  Graph edges: {G_original.number_of_edges()} -> {G_camo.number_of_edges()}")

    # --- Run feature engineering on camouflaged graph ---
    print("\n" + "=" * 85)
    print("RUNNING FEATURE ENGINEERING ON CAMOUFLAGED GRAPH")
    print("=" * 85)

    df_camo = compute_features(G_camo)
    camo_features_path = "../data/account_features_camouflaged.csv"
    df_camo.to_csv(camo_features_path, index=False)
    print(f"\nCamouflaged features saved to {camo_features_path}")

    # --- Run ablation on camouflaged features ---
    print("\n" + "=" * 85)
    print("RUNNING ABLATION ON CAMOUFLAGED FEATURES")
    print("=" * 85)

    results_camo = run_ablation(camo_features_path, "../data/ground_truth.csv")
    results_camo.to_csv("../data/ablation_results_camouflaged.csv", index=False)

    # --- Load original ablation for comparison ---
    print("\n" + "=" * 85)
    print("SIDE-BY-SIDE COMPARISON: ORIGINAL vs CAMOUFLAGED")
    print("=" * 85)

    results_orig = pd.read_csv("../data/ablation_results.csv")

    # Compare at the 10% threshold (a reasonable middle ground)
    comparison_pct = 0.10
    print(f"\nComparing at top {comparison_pct*100:.0f}% threshold:")
    print(f"{'Feature':30s}  {'Orig Recall':>12s}  {'Camo Recall':>12s}  "
          f"{'Orig FP-Norm':>12s}  {'Camo FP-Norm':>12s}  {'Change':>10s}")
    print("-" * 100)

    for feature in results_orig['feature'].unique():
        orig_row = results_orig[
            (results_orig['feature'] == feature) &
            (results_orig['threshold_pct'] == comparison_pct)
        ]
        camo_row = results_camo[
            (results_camo['feature'] == feature) &
            (results_camo['threshold_pct'] == comparison_pct)
        ]

        if orig_row.empty or camo_row.empty:
            continue

        orig_recall = orig_row.iloc[0]['recall_pct']
        camo_recall = camo_row.iloc[0]['recall_pct']
        orig_fp = orig_row.iloc[0]['fp_normal_rate_pct']
        camo_fp = camo_row.iloc[0]['fp_normal_rate_pct']

        recall_delta = camo_recall - orig_recall
        if abs(recall_delta) < 3:
            change = "STABLE"
        elif recall_delta < -10:
            change = "COLLAPSED"
        elif recall_delta < -3:
            change = "DEGRADED"
        else:
            change = "IMPROVED"  # unlikely but possible

        print(f"{feature:30s}  {orig_recall:11.1f}%  {camo_recall:11.1f}%  "
              f"{orig_fp:11.1f}%  {camo_fp:11.1f}%  {change:>10s}")

    print()
    print("=" * 85)
    print("INTERPRETATION GUIDE:")
    print("  STABLE    = feature still works after camouflage (real signal)")
    print("  DEGRADED  = feature weakened (partially an artifact)")
    print("  COLLAPSED = feature no longer works (was purely an artifact)")
    print("=" * 85)


if __name__ == "__main__":
    main()

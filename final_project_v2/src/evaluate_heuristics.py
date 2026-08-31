"""
Phase 4 evaluator: rule-by-rule breakdown against ground truth.
Run this after build_heuristics.py.

Enhanced in Phase B to include:
- Precision, F1-Score per rule
- Confusion matrix
- Comparison: heuristics-only vs heuristics + graph features (Tier 1)

Sample-size note: all metrics are computed on 48 mules / 20 hard
negatives / 480 normals. These are small-count ratios — report raw
counts alongside percentages.
"""
import pandas as pd
import os


def evaluate_rules_independently(alerts_path, ground_truth_path):
    alerts = pd.read_csv(alerts_path)
    ground_truth = pd.read_csv(ground_truth_path)

    mules = set(ground_truth[ground_truth['role'] == 'mule']['account_id'])
    hard_negatives = set(ground_truth[ground_truth['role'] == 'hard_negative']['account_id'])
    normals = set(ground_truth[ground_truth['role'] == 'normal']['account_id'])
    total_mules = len(mules)
    all_accounts = mules | hard_negatives | normals

    print(f"BASELINE: {total_mules} Mules | {len(hard_negatives)} Hard Negatives | {len(normals)} Normals\n")

    for rule in alerts['rule'].unique():
        flagged = set(alerts[alerts['rule'] == rule]['account_id'].unique())
        _print_metrics(rule, flagged, mules, hard_negatives, normals)

    # Combined heuristics
    all_flagged = set(alerts['account_id'].unique())
    print("\n--- COMBINED HEURISTICS ---")
    _print_metrics("All Rules Combined", all_flagged, mules, hard_negatives, normals)

    # Enriched system (heuristics + Tier 1 graph features) if risk scores exist
    risk_path = os.path.join(os.path.dirname(alerts_path), "account_risk_scores.csv")
    features_path = os.path.join(os.path.dirname(alerts_path), "account_features.csv")

    if os.path.exists(features_path):
        print("\n--- ENRICHED SYSTEM (Heuristics + Tier 1 Graph Features) ---")
        features = pd.read_csv(features_path)
        n = max(1, int(len(features) * 0.10))

        # Tier 1: out_degree (low) OR unique_receivers (low)
        tier1_out = set(features.nsmallest(n, 'out_degree')['account_id'])
        tier1_recv = set(features.nsmallest(n, 'unique_receivers')['account_id'])
        tier1 = tier1_out | tier1_recv

        enriched = all_flagged | tier1
        _print_metrics("Heuristics + Tier 1", enriched, mules, hard_negatives, normals)

        # Show what Tier 1 adds
        new_catches = (tier1 & mules) - (all_flagged & mules)
        print(f"  Tier 1 adds {len(new_catches)} new mule catches beyond heuristics alone")

    # Confusion matrix
    print("\n--- CONFUSION MATRIX (Combined Heuristics) ---")
    _print_confusion_matrix(all_flagged, mules, all_accounts - mules)


def _print_metrics(label, flagged, mules, hard_negatives, normals):
    """Print Recall, Precision, F1, FP rates with raw counts."""
    tp = flagged & mules
    fp_hn = flagged & hard_negatives
    fp_normal = flagged & normals
    fn = mules - flagged
    total_fp = len(fp_hn) + len(fp_normal)

    recall = len(tp) / len(mules) * 100 if mules else 0
    precision = len(tp) / len(flagged) * 100 if flagged else 0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0
    fp_norm_rate = len(fp_normal) / len(normals) * 100 if normals else 0

    print(f"[{label}]")
    print(f"  Flagged: {len(flagged)} | TP: {len(tp)}/{len(mules)} | "
          f"FP-Normal: {len(fp_normal)}/{len(normals)} | "
          f"FP-HardNeg: {len(fp_hn)}/{len(hard_negatives)}")
    print(f"  Recall:    {recall:5.1f}% ({len(tp)}/{len(mules)})")
    print(f"  Precision: {precision:5.1f}% ({len(tp)}/{len(flagged)})")
    print(f"  F1-Score:  {f1:5.1f}%")
    print(f"  FP-Normal: {fp_norm_rate:5.1f}% ({len(fp_normal)}/{len(normals)})")
    print(f"  FN (missed mules): {len(fn)}")


def _print_confusion_matrix(flagged, positives, negatives):
    """Print a simple 2x2 confusion matrix."""
    tp = len(flagged & positives)
    fn = len(positives - flagged)
    fp = len(flagged & negatives)
    tn = len(negatives - flagged)

    print(f"                  Predicted Fraud   Predicted Normal")
    print(f"  Actual Fraud       TP={tp:<6d}        FN={fn:<6d}")
    print(f"  Actual Normal      FP={fp:<6d}        TN={tn:<6d}")


if __name__ == "__main__":
    evaluate_rules_independently("../data/heuristic_alerts.csv", "../data/ground_truth.csv")


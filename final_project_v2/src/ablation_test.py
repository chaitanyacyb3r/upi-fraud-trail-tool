"""
Phase A: Per-Feature Ablation Testing

Tests each feature independently against ground truth using the SAME
methodology proven in Phase 4 (Fan-In / Layering / Rapid-Pass-Through
evaluation).

METHODOLOGY:
- For each feature, sort all accounts by suspicion level
- At EVERY threshold percentile (top 5%, 10%, 15%, 20%, 25%), report:
  - Recall (what % of 50 known mules are above threshold)
  - FP rate on normal accounts (what % of 480 normals are falsely flagged)
  - FP rate on hard negatives (what % of 20 hard-negatives are falsely flagged)
- ALL thresholds are reported — no cherry-picking after the fact.
  Sweeping percentiles and reporting only the best one would be the same
  "pick what works on the 50 examples" overfitting sin, just moved from
  model weights to threshold selection.
- Features exhibiting the "Layering failure mode" (decent recall but 20%+
  FP on normal accounts) are explicitly flagged.

EXPLICIT NON-GOAL: These numbers are NOT used to pick weights or thresholds
for a combined formula. They exist to identify which features are useful
signals vs. noise vs. dangerous false-positive generators, BEFORE any
combination is attempted.
"""

import pandas as pd


def run_ablation(features_path, ground_truth_path):
    features_df = pd.read_csv(features_path)
    gt_df = pd.read_csv(ground_truth_path)

    # Merge features with ground truth labels
    merged = features_df.merge(gt_df[['account_id', 'role']], on='account_id', how='left')

    mules = set(merged[merged['role'] == 'mule']['account_id'])
    hard_negatives = set(merged[merged['role'] == 'hard_negative']['account_id'])
    normals = set(merged[merged['role'] == 'normal']['account_id'])

    total_mules = len(mules)
    total_hn = len(hard_negatives)
    total_normals = len(normals)

    print("=" * 85)
    print("PER-FEATURE ABLATION TEST")
    print("=" * 85)
    print(f"BASELINE: {total_mules} Mules | {total_hn} Hard Negatives | {total_normals} Normals")
    print(f"Total accounts with features: {len(merged)}")
    print()
    print("Methodology: For each feature, flag the top N% most-suspicious")
    print("accounts and check overlap with known mules / normals / hard-negatives.")
    print("ALL threshold levels are reported — no cherry-picking.")
    print("=" * 85)

    # Define features and their "suspicious direction"
    #
    # Each entry: (feature_name, higher_is_suspicious, description)
    #   higher_is_suspicious = True  -> high values are suspicious, sort descending
    #   higher_is_suspicious = False -> low values are suspicious, sort ascending
    #   higher_is_suspicious = None  -> special handling (flow_ratio_distance)
    #
    # flow_ratio_distance is a DERIVED feature: |flow_ratio - 1.0|
    # Lower distance = closer to perfect pass-through = more suspicious.
    feature_configs = [
        # --- Graph structure ---
        ('pagerank', True,
         'Money-sink importance (standard AML concept)'),
        ('reverse_pagerank', True,
         'Fund-source importance (standard AML concept)'),
        ('betweenness_centrality', True,
         'Bridge position — WATCH: same popularity-signal risk as Layering'),
        ('clustering_coefficient', False,
         'Low = linear chain (fraud), High = social group (normal)'),
        ('reciprocity', False,
         'Low = one-way flow (fraud), High = mutual payments (normal)'),
        ('core_number', True,
         'Network coreness (peripheral vs. embedded)'),
        # --- Money flow ---
        ('in_degree', True,
         'Many incoming connections'),
        ('out_degree', False,
         'Few outgoing connections'),
        ('degree_imbalance', True,
         'High = pure collector (+1), Low = pure distributor (-1)'),
        ('flow_ratio_distance', None,
         'DERIVED: |flow_ratio - 1|, lower = closer to pass-through'),
        ('unique_senders', True,
         'Many distinct senders (fan-in signal)'),
        ('unique_receivers', False,
         'Few distinct receivers (concentrated outflow)'),
        ('counterparty_entropy', True,
         'High = diverse sender base (smurfing/task-scam)'),
        # --- Temporal ---
        ('avg_dwell_time_min', False,
         'Low = rapid forwarding (standard AML / FATF concept)'),
        ('min_dwell_time_min', False,
         'Low = fastest single pass-through event'),
        ('burstiness', True,
         'High = sudden activity bursts after dormancy'),
        ('off_hours_ratio', True,
         'High = unusual timing (11 PM - 5 AM)'),
        ('active_days', False,
         'Low = short-lived disposable account'),
    ]

    # Create derived feature: |flow_ratio - 1|
    # Lower distance = more suspicious (closer to perfect pass-through)
    merged['flow_ratio_distance'] = (merged['flow_ratio'] - 1.0).abs()

    # All threshold percentiles — every one is reported, no cherry-picking
    thresholds = [0.05, 0.10, 0.15, 0.20, 0.25]

    all_results = []
    verdicts = []

    for feature_name, higher_is_suspicious, description in feature_configs:
        print(f"\n{'-' * 75}")
        print(f"FEATURE: {feature_name}")
        print(f"  Signal: {description}")

        if feature_name not in merged.columns:
            print(f"  SKIPPED: column not found in features CSV")
            continue

        # Determine sort order
        if feature_name == 'flow_ratio_distance':
            ascending = True   # lower distance = more suspicious
        elif higher_is_suspicious:
            ascending = False   # high values first
        else:
            ascending = True    # low values first

        sorted_df = merged.sort_values(
            feature_name, ascending=ascending, na_position='last'
        ).reset_index(drop=True)

        feature_has_layering_problem = False
        best_recall_at_low_fp = 0.0

        for pct in thresholds:
            n = max(1, int(len(sorted_df) * pct))
            flagged_ids = set(sorted_df.head(n)['account_id'])

            tp = flagged_ids & mules
            fp_hn = flagged_ids & hard_negatives
            fp_normal = flagged_ids & normals

            recall = (len(tp) / total_mules * 100) if total_mules > 0 else 0.0
            fp_hn_rate = (len(fp_hn) / total_hn * 100) if total_hn > 0 else 0.0
            fp_normal_rate = (len(fp_normal) / total_normals * 100) if total_normals > 0 else 0.0

            # Check for Layering failure mode
            warning = ""
            if recall > 10 and fp_normal_rate >= 20:
                warning = " ** LAYERING FAILURE MODE **"
                feature_has_layering_problem = True
            elif recall > 10 and fp_normal_rate >= 10:
                warning = " !! ELEVATED FP"

            # Track best recall at <=10% normal FP rate
            if fp_normal_rate <= 10.0 and recall > best_recall_at_low_fp:
                best_recall_at_low_fp = recall

            print(f"  Top {pct * 100:4.0f}% ({n:3d} accts): "
                  f"TP={len(tp):2d} (recall {recall:5.1f}%) | "
                  f"FP-HN={len(fp_hn):2d}/{total_hn} ({fp_hn_rate:5.1f}%) | "
                  f"FP-Norm={len(fp_normal):3d}/{total_normals} ({fp_normal_rate:5.1f}%)"
                  f"{warning}")

            all_results.append({
                'feature': feature_name,
                'threshold_pct': pct,
                'n_flagged': n,
                'tp': len(tp),
                'recall_pct': round(recall, 2),
                'fp_hard_neg': len(fp_hn),
                'fp_hn_rate_pct': round(fp_hn_rate, 2),
                'fp_normal': len(fp_normal),
                'fp_normal_rate_pct': round(fp_normal_rate, 2),
            })

        # ---- Verdict ----
        if feature_has_layering_problem:
            verdict = ("DANGEROUS -- same problem as Layering heuristic "
                       "(decent recall but high FP on innocent accounts)")
            symbol = "[WARN]"
        elif best_recall_at_low_fp >= 30:
            verdict = ("USEFUL -- meaningful recall with controlled false positives "
                       f"(best recall {best_recall_at_low_fp:.1f}% at <=10% normal FP)")
            symbol = "[OK]"
        elif best_recall_at_low_fp >= 10:
            verdict = ("MARGINAL -- some signal but weak "
                       f"(best recall {best_recall_at_low_fp:.1f}% at <=10% normal FP)")
            symbol = "[WEAK]"
        else:
            verdict = "NOISE -- no useful separation at acceptable FP rates"
            symbol = "[X]"

        print(f"  VERDICT: {symbol} {verdict}")
        verdicts.append({'feature': feature_name, 'verdict': verdict})

    # ---- Summary Table ----
    print(f"\n{'=' * 85}")
    print("ABLATION SUMMARY")
    print(f"{'=' * 85}")
    for v in verdicts:
        status = v['verdict'].split('--')[0].strip()
        print(f"  {v['feature']:30s}  {status}")
    print(f"{'=' * 85}")

    results_df = pd.DataFrame(all_results)
    return results_df


if __name__ == "__main__":
    results = run_ablation(
        "../data/account_features.csv",
        "../data/ground_truth.csv"
    )
    output_path = "../data/ablation_results.csv"
    results.to_csv(output_path, index=False)
    print(f"\nDetailed results saved to {output_path}")

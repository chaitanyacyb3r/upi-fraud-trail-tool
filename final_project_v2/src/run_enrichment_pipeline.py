"""
Phase B Enrichment Pipeline — Master Orchestrator

Runs all Phase B components in order:
1. Feature Engineering (compute graph/flow/temporal features)
2. Risk Score (Tier 1: out_degree + unique_receivers)
3. Community Detection (Louvain unsupervised clustering)
4. Benford's Law Analysis (Chi-square first-digit test)
5. Enhanced Evaluation (Precision, F1, Confusion Matrix)

Run from the src/ directory: python run_enrichment_pipeline.py
"""

import os
import sys


def main():
    print("=" * 70)
    print("PHASE B: ENRICHMENT PIPELINE")
    print("=" * 70)

    # Step 1: Feature Engineering
    print("\n[1/5] Feature Engineering...")
    from feature_engineering import load_graph, compute_features
    G = load_graph("../data/forensic_network.gpickle")
    features_df = compute_features(G)
    features_df.to_csv("../data/account_features.csv", index=False)
    print("  -> Saved account_features.csv")

    # Step 2: Risk Score
    print("\n[2/5] Risk Score Computation...")
    from risk_score import compute_risk_scores
    compute_risk_scores("../data/account_features.csv",
                        "../data/account_risk_scores.csv")

    # Step 3: Community Detection
    print("\n[3/5] Louvain Community Detection...")
    try:
        from community_detection import detect_communities
        detect_communities(
            "../data/forensic_network.gpickle",
            risk_scores_path="../data/account_risk_scores.csv",
            ground_truth_path="../data/ground_truth.csv",
            output_path="../data/detected_communities.csv"
        )
    except ImportError as e:
        print(f"  SKIPPED (missing dependency): {e}")
        print("  Install with: pip install python-louvain")

    # Step 4: Benford's Analysis
    print("\n[4/5] Benford's Law Analysis...")
    try:
        from benford_analysis import run_benford_analysis
        run_benford_analysis(
            "../data/normalized_transactions_v3.csv",
            "../data/benford_results.csv"
        )
    except ImportError as e:
        print(f"  SKIPPED (missing dependency): {e}")
        print("  Install with: pip install scipy")

    # Step 5: Enhanced Evaluation
    print("\n[5/5] Enhanced Evaluation...")
    from evaluate_heuristics import evaluate_rules_independently
    evaluate_rules_independently("../data/heuristic_alerts.csv",
                                 "../data/ground_truth.csv")

    print("\n" + "=" * 70)
    print("PIPELINE COMPLETE")
    print("=" * 70)
    print("\nGenerated files:")
    for f in ["account_features.csv", "account_risk_scores.csv",
              "detected_communities.csv", "detected_communities_accounts.csv",
              "benford_results.csv"]:
        path = f"../data/{f}"
        status = "OK" if os.path.exists(path) else "MISSING"
        print(f"  [{status}] data/{f}")


if __name__ == "__main__":
    main()

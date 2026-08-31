"""
Risk Score Enrichment — Tier 1 Only

Uses ONLY the two features that survived two rounds of camouflage
stress-testing (social circles + full volume):
  - out_degree: few outgoing connections (mules send to 1-2 cashout accounts)
  - unique_receivers: few distinct recipients

These features are combined into a transparent, auditable risk score.

WHAT THIS IS NOT:
  - Not a trained ML model (deliberate — see docs/methodology_notes.md)
  - Not fitted to our ground truth (weights from domain reasoning)
  - Not a probability ("80% likely fraud") — it's a prioritization score

Weight rationale:
  Both features measure the same structural property (concentrated outflow),
  validated independently through ablation + camouflage. Equal weighting is
  the honest default when domain literature doesn't justify asymmetry.
  These weights were NOT chosen by inspecting which values separate known
  mules from normals in this dataset.
"""

import pandas as pd
import numpy as np


def compute_risk_scores(features_path, output_path=None):
    """Compute risk scores for all accounts using Tier 1 features only.

    Score = 0.5 * normalized(out_degree, inverted) +
            0.5 * normalized(unique_receivers, inverted)

    Both are min-max normalized then INVERTED (low raw value = high risk).
    Score range: 0.0 (lowest risk) to 1.0 (highest risk).
    """
    df = pd.read_csv(features_path)

    # Min-max normalize then INVERT: low out_degree = high risk
    def invert_normalize(series):
        mn, mx = series.min(), series.max()
        if mx == mn:
            return pd.Series(0.5, index=series.index)
        normalized = (series - mn) / (mx - mn)
        return 1.0 - normalized  # invert: low raw = high score

    out_deg_score = invert_normalize(df['out_degree'])
    uniq_recv_score = invert_normalize(df['unique_receivers'])

    # Equal weights — domain reasoning: both measure the same structural
    # property (concentrated outflow). No asymmetry justified by literature.
    df['risk_score'] = 0.5 * out_deg_score + 0.5 * uniq_recv_score

    # Risk tier for investigator readability
    df['risk_tier'] = pd.cut(
        df['risk_score'],
        bins=[0, 0.3, 0.6, 0.8, 1.01],
        labels=['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'],
        right=False
    )

    # Component scores for transparency (investigator can see WHY)
    df['score_out_degree'] = out_deg_score
    df['score_unique_receivers'] = uniq_recv_score

    print(f"Risk scores computed for {len(df)} accounts")
    print(f"  CRITICAL: {(df['risk_tier']=='CRITICAL').sum()}")
    print(f"  HIGH:     {(df['risk_tier']=='HIGH').sum()}")
    print(f"  MEDIUM:   {(df['risk_tier']=='MEDIUM').sum()}")
    print(f"  LOW:      {(df['risk_tier']=='LOW').sum()}")

    if output_path:
        df.to_csv(output_path, index=False)
        print(f"Saved to {output_path}")

    return df


if __name__ == "__main__":
    df = compute_risk_scores(
        "../data/account_features.csv",
        "../data/account_risk_scores.csv"
    )

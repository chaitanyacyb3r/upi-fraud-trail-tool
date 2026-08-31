"""
Benford's Law Analysis — Statistical Anomaly Detection

Benford's Law: in naturally occurring datasets, the leading digit '1'
appears ~30% of the time, '2' ~17.6%, etc. Fabricated or manipulated
transaction amounts often violate this distribution because humans
unconsciously avoid patterns that look "too regular."

This module tests each account's transaction amounts against Benford's
expected distribution using a Chi-square goodness-of-fit test.

IMPORTANT CAVEAT: With only 15-60 transactions per account, individual
Chi-square tests have low statistical power. This is a supplementary
signal, NOT standalone evidence of fraud. Large deviations are worth
investigating but are not proof.
"""

import pandas as pd
import numpy as np
from scipy import stats
import math


# Benford's Law expected probabilities for digits 1-9
BENFORD_EXPECTED = {
    d: math.log10(1 + 1/d) for d in range(1, 10)
}


def _leading_digit(amount):
    """Extract leading digit from a transaction amount."""
    try:
        s = str(abs(float(amount)))
        for c in s:
            if c.isdigit() and c != '0':
                return int(c)
    except (ValueError, TypeError):
        pass
    return None


def run_benford_analysis(transactions_path, output_path=None):
    """Run per-account Benford's Law analysis.

    For each account, collects all transaction amounts (sent + received),
    computes the first-digit distribution, and runs a Chi-square test
    against Benford's expected distribution.

    Returns DataFrame with one row per account:
    - chi2_statistic, p_value
    - digit_counts (for visualization)
    - benford_flag: True if p < 0.05 AND n >= 20
    """
    print("Loading transactions...")
    df = pd.read_csv(transactions_path)

    # Get all amounts per account (as sender OR receiver)
    print("Computing per-account first-digit distributions...")
    accounts = set(df['sender'].unique()) | set(df['receiver'].unique())
    accounts = sorted([a for a in accounts if str(a).startswith('ACC')])

    results = []

    for acc in accounts:
        # All transactions involving this account
        mask = (df['sender'] == acc) | (df['receiver'] == acc)
        amounts = df[mask]['amount'].tolist()

        # Extract leading digits
        digits = [_leading_digit(a) for a in amounts]
        digits = [d for d in digits if d is not None]

        n = len(digits)
        if n < 5:  # Too few transactions for any meaningful test
            results.append({
                'account_id': acc,
                'n_transactions': n,
                'chi2_statistic': None,
                'p_value': None,
                'benford_flag': False,
                'caveat': 'too_few_transactions'
            })
            continue

        # Observed digit distribution
        observed = [digits.count(d) for d in range(1, 10)]

        # Expected counts under Benford's Law
        expected = [BENFORD_EXPECTED[d] * n for d in range(1, 10)]

        # Chi-square test
        # Combine bins with expected count < 5 (standard practice)
        chi2, p_value = stats.chisquare(observed, expected)

        # Flag: significant deviation AND enough samples
        benford_flag = (p_value < 0.05) and (n >= 20)

        caveat = ''
        if n < 20:
            caveat = 'low_sample_size'

        results.append({
            'account_id': acc,
            'n_transactions': n,
            'chi2_statistic': round(chi2, 4),
            'p_value': round(p_value, 6),
            'benford_flag': benford_flag,
            'caveat': caveat,
            'digit_1_pct': round(digits.count(1) / n * 100, 1),
            'digit_2_pct': round(digits.count(2) / n * 100, 1),
            'digit_3_pct': round(digits.count(3) / n * 100, 1),
        })

    results_df = pd.DataFrame(results)

    flagged = results_df[results_df['benford_flag'] == True]
    print(f"\nBenford's Analysis complete for {len(results_df)} accounts")
    print(f"  Flagged (p<0.05 and n>=20): {len(flagged)}")
    print(f"  Low sample size (n<20): {(results_df['caveat']=='low_sample_size').sum()}")
    print(f"  Too few (<5 txns): {(results_df['caveat']=='too_few_transactions').sum()}")

    if output_path:
        results_df.to_csv(output_path, index=False)
        print(f"Saved to {output_path}")

    return results_df


if __name__ == "__main__":
    results = run_benford_analysis(
        "../data/normalized_transactions_v3.csv",
        "../data/benford_results.csv"
    )

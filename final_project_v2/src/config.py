"""
Calibration config for the synthetic dataset generator.

Every number in here is either:
  (a) taken directly from a verified real statistic, with a citation, or
  (b) an explicitly-labeled assumption we're making for demo purposes.

This file IS your "data generation methodology note" in code form —
when you write the half-page methodology doc, you're basically
transcribing this file into prose.
"""

# ---------------------------------------------------------------------------
# SCALE (Section 7.3 of project docs)
# ---------------------------------------------------------------------------
NUM_NORMAL_ACCOUNTS = 480          # everyday, non-fraud accounts
NUM_HARD_NEGATIVE_ACCOUNTS = 20    # legitimate but "look suspicious" accounts
NUM_FRAUD_RING_ACCOUNTS = 50       # accounts that are part of an injected fraud ring
# total ~550 accounts, in the 500-1000 target range

SIMULATION_DAYS = 60               # 2 months of transaction history

# ---------------------------------------------------------------------------
# NORMAL TRANSACTION CALIBRATION
# Source: NPCI/RBI reporting, average UPI ticket size ~Rs 1,293 in 2025
# (down from Rs 1,600+ in early 2023)
# ---------------------------------------------------------------------------
NORMAL_TXN_AMOUNT_MEDIAN = 1293       # matches real average UPI ticket size
NORMAL_TXN_AMOUNT_SIGMA = 0.9         # log-normal spread -> mostly small, long tail

# Roughly how many normal transactions per account over the whole window.
# This is a demo-scale ASSUMPTION, not a cited stat -- documented as such.
NORMAL_TXN_PER_ACCOUNT_MIN = 15
NORMAL_TXN_PER_ACCOUNT_MAX = 60

# ---------------------------------------------------------------------------
# FRAUD LOSS CALIBRATION
# Source: reported ranges for high-value targeted scams (investment scams,
# "digital arrest" scams) commonly Rs 2 lakh - Rs 25 lakh per victim.
# ---------------------------------------------------------------------------
FRAUD_VICTIM_LOSS_MIN = 200_000
FRAUD_VICTIM_LOSS_MAX = 2_500_000

# Fan-in fraud (task-scam style): many small deposits from many "victim-like"
# source accounts converging on one mule account.
FAN_IN_DEPOSIT_MIN = 500
FAN_IN_DEPOSIT_MAX = 5000
FAN_IN_CONTRIBUTOR_COUNT_MIN = 15
FAN_IN_CONTRIBUTOR_COUNT_MAX = 40

# ---------------------------------------------------------------------------
# FRAUD DENSITY -- DELIBERATELY INFLATED FOR DEMO PURPOSES
# Real-world fraud rate is a tiny fraction of a percent of accounts/transactions.
# For a demo to be usable, we need the signal to be findable, so we inflate
# fraud-linked accounts to ~9% of the population (50 / 550) instead of the
# real-world ~0.01% range. THIS IS DOCUMENTED, NOT HIDDEN.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# TIMING REALISM
# "Rapid pass-through" only means something if normal accounts DON'T behave
# this way. Fraud hops happen within minutes-to-hours; normal transactions
# are spread naturally across the day.
# ---------------------------------------------------------------------------
FRAUD_HOP_DELAY_MIN_MINUTES = 5
FRAUD_HOP_DELAY_MAX_MINUTES = 180   # up to 3 hours

# ---------------------------------------------------------------------------
# NARRATION / FORMAT REALISM
# Modeled on PhonePe's real CSV export columns (verified from your own
# downloaded statement) and general Indian bank narration conventions
# (verified via statementsparser / AgamiAI dataset structure).
# ---------------------------------------------------------------------------
PHONEPE_CSV_COLUMNS = [
    "Date", "Time", "Transaction Details", "Transaction ID",
    "UTR", "Transaction Type", "Credit/Debit Instrument", "Amount",
]

BANK_CODES_FOR_MASKED_ACCOUNTS = ["HDFC", "SBI", "ICICI", "AXIS", "KOTAK", "PNB"]

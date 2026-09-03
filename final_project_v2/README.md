# UPI Fraud Money-Trail Reconstruction Tool

Status: Phases 1-6 complete and verified end-to-end. Phase B (graph-structural
enrichment) complete — adds validated risk scoring, unsupervised fraud ring
discovery, Benford's Law analysis, and enhanced evaluation metrics.

## Setup
```
pip install pandas numpy faker networkx pyvis streamlit reportlab
pip install python-louvain scipy plotly    # Phase B dependencies
```

## Quick Start (data/ already included, no regeneration needed)

### Run the investigator dashboard
```
cd src
streamlit run app.py
```
Pick an alert from the sidebar. Fan-In alerts show all edges in red;
Layering alerts show yellow-highlighted exact evidence paths. Click
"Generate Form 'A' Report" to produce a Delhi HC Form 'A' PDF.

### Run the Phase B enrichment pipeline
```
cd src
python run_enrichment_pipeline.py
```
This runs all enrichment steps in order: feature engineering, risk
scoring, Louvain community detection, Benford's Law analysis, and
enhanced evaluation. Outputs are saved to `data/`.

## To regenerate everything from scratch (optional)
```
cd src
python generate_dataset.py        # Phase 1: synthetic data
python ingest_statements.py       # Phase 2: parse statements
python build_graph.py             # Phase 3: build transaction graph
python build_heuristics.py        # Phase 4: detect fraud
python evaluate_heuristics.py     # Phase 4: evaluate detection
python run_enrichment_pipeline.py # Phase B: enrichment layer
```

## Architecture

```
Phase 1: Generate synthetic data (548 accounts, 20,000+ transactions)
    |
Phase 2: Ingest bank statements (CSV parsing, entity resolution)
    |
Phase 3: Build forensic graph (NetworkX MultiDiGraph, UTR-keyed edges)
    |
Phase 4: Detect fraud (Fan-In heuristic + Tier 1 graph features)
    |
Phase B: Enrichment (risk scores, community detection, Benford's Law)
    |
Phase 5: Investigator dashboard (Streamlit)
    |
Phase 6: Court-ready PDF export (Delhi HC Form 'A')
```

## Detection System — Verified Performance

### Primary Detection: Fan-In + Tier 1 Graph Features (RECOMMENDED)

| System | Recall | FP-Normal | FP-HardNeg | Precision | Flagged |
|--------|--------|-----------|------------|-----------|---------|
| Fan-In alone | 54.0% (27/50) | 0.0% (0/480) | 0.0% (0/20) | 100% | 27 |
| **Fan-In + Tier 1** | **95.8% (46/48)** | **1.7% (8/480)** | **0.0% (0/20)** | **85.2%** | **54** |

Tier 1 features (`out_degree`, `unique_receivers`) were validated through:
1. Per-feature ablation testing at 5 threshold percentiles (no cherry-picking)
2. Two rounds of camouflage stress-testing (10-25 txns + 30-60 txns with
   social circles) to confirm signals survive when mules have normal activity

Features that FAILED camouflage testing (correctly dropped):
- `avg_dwell_time`: 85.4% → 16.7% recall (artifact of zero normal activity)
- `reciprocity`: 95.8% → 66.7% (inflated by random one-off camouflage partners)
- `clustering_coefficient`: 47.9% → 18.8% (artifact of no social connections)

### Secondary: Layering (Tier 2, low-confidence)
14-28% recall, ~30% false positives. Excluded from the enriched system.
Documented as an honest limitation — timing+amount alone cannot cleanly
separate 2-hop layering from dense social payment graphs.

## Phase B: Enrichment Layer

### Risk Scoring (`risk_score.py`)
Transparent, auditable risk score using only camouflage-validated features:
- `out_degree` (few outgoing connections = suspicious)
- `unique_receivers` (few distinct recipients = suspicious)
- Equal weights (0.5 each) from domain reasoning, NOT fitted to ground truth
- Score range: 0.0 (lowest risk) to 1.0 (highest risk)
- Risk tiers: LOW / MEDIUM / HIGH / CRITICAL

### Community Detection (`community_detection.py`)
Louvain unsupervised clustering on the transaction graph. Key finding:
**7/7 multi-account layering rings perfectly isolated by unsupervised
clustering — zero labels used.**

| Community | Size | Mules | Mule % | Discovery |
|-----------|------|-------|--------|-----------|
| 3 (main)  | ~500 | 20    | ~4%    | Normal population |
| 4         | 17   | 7     | 41.2%  | Fan-in mule cluster |
| 0,1,2,5,6,7,8,9 | 4-6 each | 3 each | 50-75% | Layering chains (A→B→C) |

Each of the 7 small communities corresponds to an actual layering ring,
verified against ground-truth ring IDs (approach A: genuine validation,
not structural self-consistency). The 27 single-mule fan-in accounts
cluster into only 3 communities by shared victim pools — a real
structural finding reported separately since single-account "rings"
can't fail the community-match test by definition.

### Benford's Law Analysis (`benford_analysis.py`)
Chi-square test of first-digit distributions against Benford's Law.
Status: **Exploratory / low-confidence.** 43 accounts flagged (16% recall,
6% FP-Normal, 18.6% precision). With only 15-60 transactions per account,
statistical power is low — a null result means "we can't tell," not
"no fraud." Presented as supplementary context, not detection.

### Enhanced Evaluation (`evaluate_heuristics.py`)
Now reports Precision, F1-Score, and Confusion Matrix alongside Recall
and FP rates. Includes automatic comparison of heuristics-only vs
enriched system when feature data is available.

## What's verified, and how

Every fix was independently confirmed against real generated data:

- Fan-In: 54% recall, 0% false positives on both hard-negative and
  normal accounts — the reliable, primary (Tier 1) heuristic.
- Tier 1 graph features: survived two rounds of camouflage testing.
  Features that collapsed (avg_dwell_time, clustering_coefficient) were
  correctly dropped before inclusion.
- Community detection: 7/7 multi-account layering rings perfectly
  isolated — verified against ground-truth ring IDs (genuine validation,
  not structural self-consistency).
- Entity resolution: duplicate Faker-generated names are quarantined
  (tagged AMBIGUOUS) rather than silently dropped or merged.
- Graph: MultiDiGraph (not DiGraph) — repeat transactions between the
  same two accounts preserved as distinct edges.
- evidence_path column: stores the EXACT UTRs of specific transactions
  that triggered a Layering alert, not just account IDs.
- PDF reports: Delhi HC Form 'A' with Section 63 BSA certification.
  Verified: Layering PDF produces exactly 2 correct exhibit rows;
  Fan-In PDF produces 38 correct rows.

## Known limitations (documented, not oversights)

- **No holdout set.** All metrics were computed on the same 548-account
  population used to derive thresholds. A genuine holdout or independently
  generated dataset would be needed to confirm generalization.
- **Sample-size honesty.** "95.8% recall" is 46/48 mules. "0% FP on hard
  negatives" is 0/20. These are small-count ratios — a couple of accounts
  swinging either way meaningfully changes the percentages.
- **Synthetic data artifacts.** Mule accounts are generated with structural
  properties that may not match real-world mules (limited transaction
  history, predictable timing patterns, no cross-ring transactions).
  Camouflage tests partially address this but don't eliminate it.
- **No supervised ML by design.** 50 labeled fraud examples from one
  generator is insufficient for supervised learning. See
  `docs/methodology_notes.md` for full rationale.
- fraud_storylines.py's fan_out_layering storyline never generates any
  rings (mule-account allocation bug exhausts the pool first).
- Rapid Pass-Through heuristic was tried and dropped entirely (0% recall).
- Faker has no cross-machine name reproducibility even with the same seed.

## File guide

### Phase 1 (synthetic data)
`config.py`, `accounts.py`, `normal_transactions.py`, `hard_negatives.py`,
`fraud_storylines.py`, `export.py`, `export_account_mapping.py`,
`generate_dataset.py`

### Phase 2 (ingestion)
`ingest_statements.py`

### Phase 3 (graph)
`build_graph.py`

### Phase 4 (detection)
`build_heuristics.py`, `evaluate_heuristics.py`

### Phase B (enrichment)
`feature_engineering.py` — computes 18 graph/flow/temporal features per account
`risk_score.py` — transparent risk scoring (Tier 1 features only)
`community_detection.py` — Louvain unsupervised fraud ring discovery
`benford_analysis.py` — per-account Benford's Law Chi-square test
`run_enrichment_pipeline.py` — master orchestrator for all Phase B steps
`ablation_test.py` — per-feature independent testing at 5 threshold percentiles
`camouflage_retest.py` — validation: do features survive when mules have normal activity?

### Phase 5 (visualization)
`app.py`

### Phase 6 (report export)
`export_report.py`

### Documentation
`docs/methodology_notes.md` — full methodology: why ML was dropped, feature
selection process, camouflage testing, weight rationale, all known limitations

### Data files
`data/` — pre-generated, fully consistent dataset including:
- `account_features.csv` — 548 accounts x 21 features
- `account_risk_scores.csv` — risk scores + tiers for all accounts
- `detected_communities.csv` — 9 Louvain communities with mule counts
- `detected_communities_accounts.csv` — per-account community assignments
- `benford_results.csv` — per-account Benford's Law test results
- `ablation_results.csv` — per-feature ablation metrics at all thresholds
- `forensic_network.gpickle` — the transaction graph
- `ground_truth.csv`, `ground_truth_transactions.csv` — labels (eval only)
- `heuristic_alerts.csv` — Fan-In and Layering alerts
- `normalized_transactions_v3.csv` — all parsed transactions
- `account_mapping.csv` — name-to-account resolution

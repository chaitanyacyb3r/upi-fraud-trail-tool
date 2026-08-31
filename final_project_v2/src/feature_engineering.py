"""
Phase A: Feature Engineering for UPI Fraud Detection

Computes graph-structural, money-flow, and temporal features for every
resolved account in the forensic network graph.

METHODOLOGY NOTE: These features are enrichments for transparent scoring.
They are NOT inputs to a trained ML model — see docs/methodology_notes.md
for why supervised ML was deliberately not used with this dataset (50
labeled fraud examples from a single synthetic generator is insufficient
for trustworthy supervised learning).

Domain rationale for each feature is documented inline. References marked
"standard AML concept" indicate well-known anti-money laundering techniques
without a specific verified paper citation — we do not present unverified
citations as authoritative.
"""

import networkx as nx
import pandas as pd
import numpy as np
import pickle
import math
from collections import defaultdict


def load_graph(graph_path):
    print(f"Loading graph from {graph_path}...")
    with open(graph_path, 'rb') as f:
        return pickle.load(f)


def _build_simple_digraph(G):
    """Convert MultiDiGraph to simple DiGraph with summed edge weights.
    Required because PageRank, betweenness centrality, etc. may not
    handle multi-edges correctly in NetworkX."""
    simple = nx.DiGraph()
    for node, attr in G.nodes(data=True):
        simple.add_node(node, **attr)
    for u, v, data in G.edges(data=True):
        amt = float(data.get('amount', 0))
        if simple.has_edge(u, v):
            simple[u][v]['weight'] += amt
        else:
            simple.add_edge(u, v, weight=amt)
    return simple


def _parse_timestamps(G):
    """Pre-parse all edge timestamps into datetime objects."""
    parsed_count = 0
    failed_count = 0
    for u, v, k, data in G.edges(keys=True, data=True):
        try:
            data['parsed_ts'] = pd.to_datetime(data['timestamp'])
            parsed_count += 1
        except Exception:
            data['parsed_ts'] = None
            failed_count += 1
    print(f"  Parsed {parsed_count} timestamps ({failed_count} failures)")


def compute_features(G):
    """Compute all features for every resolved ACC* node in the graph.

    Returns a DataFrame with one row per account and columns for each feature.
    """
    print("\n--- FEATURE ENGINEERING ---")

    print("Step 1/6: Parsing edge timestamps...")
    _parse_timestamps(G)

    print("Step 2/6: Building simplified DiGraph for centrality metrics...")
    simple_G = _build_simple_digraph(G)
    simple_undirected = simple_G.to_undirected()

    # ---- Global graph metrics ----

    print("Step 3/6: Computing global graph metrics...")

    # PageRank: standard AML concept — identifies money sinks (accounts
    # where value accumulates) in financial flow graphs.
    # WARNING: may also flag legitimately popular accounts — ablation will check.
    pr = nx.pagerank(simple_G, weight='weight')

    # Reverse PageRank: standard AML concept — identifies primary fund
    # source/victim nodes (where money originates).
    rev_G = simple_G.reverse()
    rev_pr = nx.pagerank(rev_G, weight='weight')

    # Betweenness Centrality: standard AML concept — identifies bridge
    # accounts sitting on shortest paths between clusters. In layering
    # schemes, intermediaries have high betweenness.
    # WARNING: well-connected social hubs also have high betweenness —
    # same "popularity signal" problem as the Layering heuristic.
    bc = nx.betweenness_centrality(simple_G, weight='weight')

    # Clustering Coefficient: standard network analysis concept.
    # Low clustering = linear chain topology (fraud pattern).
    # High clustering = dense social group (normal payment behavior).
    cc = nx.clustering(simple_undirected)

    # Core Number (k-core decomposition): standard graph decomposition.
    # Distinguishes peripheral accounts from deeply embedded participants.
    # Freshly recruited mule accounts tend to be peripheral.
    try:
        cn = nx.core_number(simple_undirected)
    except Exception:
        cn = {n: 0 for n in simple_G.nodes()}

    # ---- Per-node features ----

    print("Step 4/6: Identifying resolved account nodes...")
    resolved_nodes = sorted([
        n for n, attr in G.nodes(data=True)
        if attr.get('node_type') == 'resolved' and n.startswith('ACC')
    ])
    print(f"  Found {len(resolved_nodes)} resolved ACC* nodes")

    print("Step 5/6: Computing per-node flow, temporal, and reciprocity features...")
    features = []

    for i, node in enumerate(resolved_nodes):
        if (i + 1) % 100 == 0:
            print(f"  Processing account {i + 1}/{len(resolved_nodes)}...")

        in_edges = list(G.in_edges(node, keys=True, data=True))
        out_edges = list(G.out_edges(node, keys=True, data=True))

        in_deg = len(in_edges)
        out_deg = len(out_edges)

        # ---- Money Flow Features ----

        total_in = sum(float(d['amount']) for _, _, _, d in in_edges) if in_edges else 0.0
        total_out = sum(float(d['amount']) for _, _, _, d in out_edges) if out_edges else 0.0

        # Degree imbalance: (in - out) / (in + out)
        # +1.0 = pure collector (all incoming, no outgoing)
        # -1.0 = pure distributor (all outgoing, no incoming)
        deg_imbalance = ((in_deg - out_deg) / (in_deg + out_deg)
                         if (in_deg + out_deg) > 0 else 0.0)

        # Flow ratio: total_out / total_in
        # Near 1.0 = pass-through (money in ≈ money out)
        # Already partially validated via the 85-105% conservation band
        # in the existing Fan-In and Layering heuristics.
        flow_ratio = total_out / total_in if total_in > 0 else 0.0

        # Unique counterparties
        unique_senders = len(set(u for u, _, _, _ in in_edges))
        unique_receivers = len(set(v for _, v, _, _ in out_edges))

        # Counterparty entropy (Shannon entropy of sender volume shares)
        # Standard information-theoretic measure. High entropy = receiving
        # equal-sized payments from many diverse sources (smurfing/task-scam).
        # Low entropy = dominated by a few regular counterparties (normal).
        sender_volumes = defaultdict(float)
        for u, _, _, d in in_edges:
            sender_volumes[u] += float(d['amount'])
        if sender_volumes and total_in > 0:
            probs = [v / total_in for v in sender_volumes.values()]
            counterparty_entropy = -sum(p * math.log2(p) for p in probs if p > 0)
        else:
            counterparty_entropy = 0.0

        # ---- Reciprocity ----
        # Standard financial network metric. Normal accounts have mutual
        # payment relationships (friends, family). Fraud flows are strictly
        # one-directional (Victim -> Mule1 -> Mule2).
        successors = set(v for _, v, _, _ in out_edges)
        predecessors = set(u for u, _, _, _ in in_edges)
        all_counterparties = successors | predecessors
        reciprocal = successors & predecessors
        reciprocity = (len(reciprocal) / len(all_counterparties)
                       if all_counterparties else 0.0)

        # ---- Temporal Features ----

        in_timestamps = []
        for _, _, _, d in in_edges:
            ts = d.get('parsed_ts')
            if ts is not None and not pd.isna(ts):
                in_timestamps.append(ts)

        out_timestamps = []
        for _, _, _, d in out_edges:
            ts = d.get('parsed_ts')
            if ts is not None and not pd.isna(ts):
                out_timestamps.append(ts)

        in_timestamps.sort()
        out_timestamps.sort()
        all_timestamps = sorted(in_timestamps + out_timestamps)

        # Dwell time: time between receiving money and next outgoing txn.
        # Standard AML concept (FATF typologies on layering). Rapid
        # pass-through (minutes to hours) is a core indicator.
        dwell_times = []
        if in_timestamps and out_timestamps:
            for in_ts in in_timestamps:
                for out_ts in out_timestamps:
                    if out_ts > in_ts:
                        dwell_minutes = (out_ts - in_ts).total_seconds() / 60.0
                        dwell_times.append(dwell_minutes)
                        break  # only the FIRST outgoing after this incoming

        avg_dwell = float(np.mean(dwell_times)) if dwell_times else 999999.0
        min_dwell = float(min(dwell_times)) if dwell_times else 999999.0

        # Burstiness: (σ - μ) / (σ + μ) of inter-transaction arrival times
        # Standard concept in temporal network analysis. High burstiness =
        # sudden activity bursts after prolonged dormancy (characteristic of
        # freshly activated mule accounts).
        if len(all_timestamps) >= 3:
            inter_times = [
                (all_timestamps[i + 1] - all_timestamps[i]).total_seconds() / 60.0
                for i in range(len(all_timestamps) - 1)
            ]
            mu = float(np.mean(inter_times))
            sigma = float(np.std(inter_times))
            burstiness = (sigma - mu) / (sigma + mu) if (sigma + mu) > 0 else 0.0
        else:
            burstiness = 0.0

        # Off-hours ratio: proportion of txns during 11 PM - 5 AM
        # Standard suspicious activity indicator in bank compliance
        # frameworks (general banking practice).
        if all_timestamps:
            off_hours_count = sum(
                1 for ts in all_timestamps if ts.hour >= 23 or ts.hour < 5
            )
            off_hours_ratio = off_hours_count / len(all_timestamps)
        else:
            off_hours_ratio = 0.0

        # Active days: unique days with transactions.
        # Short active window suggests disposable mule account.
        if all_timestamps:
            active_days = len(set(ts.date() for ts in all_timestamps))
        else:
            active_days = 0

        features.append({
            'account_id': node,
            # Graph structure
            'pagerank': pr.get(node, 0.0),
            'reverse_pagerank': rev_pr.get(node, 0.0),
            'betweenness_centrality': bc.get(node, 0.0),
            'clustering_coefficient': cc.get(node, 0.0),
            'reciprocity': reciprocity,
            'core_number': cn.get(node, 0),
            # Money flow
            'in_degree': in_deg,
            'out_degree': out_deg,
            'degree_imbalance': deg_imbalance,
            'flow_ratio': flow_ratio,
            'total_inflow': total_in,
            'total_outflow': total_out,
            'unique_senders': unique_senders,
            'unique_receivers': unique_receivers,
            'counterparty_entropy': counterparty_entropy,
            # Temporal
            'avg_dwell_time_min': avg_dwell,
            'min_dwell_time_min': min_dwell,
            'burstiness': burstiness,
            'off_hours_ratio': off_hours_ratio,
            'active_days': active_days,
        })

    df = pd.DataFrame(features)

    print(f"\nStep 6/6: Sanity checks...")
    print(f"  Total accounts: {len(df)}")
    nan_cols = [c for c in df.columns if df[c].isna().any()]
    print(f"  Columns with NaN: {nan_cols if nan_cols else 'None'}")
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    inf_cols = [c for c in numeric_cols if np.isinf(df[c]).any()]
    print(f"  Columns with Inf: {inf_cols if inf_cols else 'None'}")

    return df


if __name__ == "__main__":
    G = load_graph("../data/forensic_network.gpickle")
    df = compute_features(G)

    output_path = "../data/account_features.csv"
    df.to_csv(output_path, index=False)
    print(f"\nFeatures saved to {output_path}")
    print(f"Columns ({len(df.columns)}): {list(df.columns)}")

    # Print summary statistics for key features
    print(f"\n--- FEATURE SUMMARY STATISTICS ---")
    for col in df.columns:
        if col == 'account_id':
            continue
        print(f"  {col:30s}  min={df[col].min():12.4f}  "
              f"median={df[col].median():12.4f}  max={df[col].max():12.4f}")

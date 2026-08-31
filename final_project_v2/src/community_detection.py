"""
Louvain Community Detection — Unsupervised Fraud Ring Discovery

No labels needed, no overfitting possible. Louvain partitions the
transaction graph into communities (clusters of accounts that transact
heavily with each other). Fraud rings — groups of mules receiving from
the same victims and forwarding to the same cashout points — naturally
form tight communities.

After detection, each community is cross-referenced with ground truth
(for evaluation) and risk scores (for investigator use).
"""

import networkx as nx
import pandas as pd
import pickle

try:
    import community as community_louvain
except ImportError:
    print("ERROR: python-louvain not installed. Run: pip install python-louvain")
    raise


def detect_communities(graph_path, risk_scores_path=None, ground_truth_path=None,
                       output_path=None):
    """Run Louvain community detection on the transaction graph.

    Returns a DataFrame with one row per community, including:
    - member list, size
    - internal transaction volume
    - average risk score (if risk_scores provided)
    - mule count and fraction (if ground_truth provided)
    """
    print("Loading graph...")
    with open(graph_path, 'rb') as f:
        G = pickle.load(f)

    # Louvain needs undirected graph — convert with summed edge weights
    print("Converting to undirected weighted graph...")
    G_simple = nx.Graph()
    for u, v, data in G.edges(data=True):
        amt = float(data.get('amount', 0))
        if G_simple.has_edge(u, v):
            G_simple[u][v]['weight'] += amt
        else:
            G_simple.add_edge(u, v, weight=amt)

    # Only include resolved ACC* nodes
    acc_nodes = [n for n in G_simple.nodes() if str(n).startswith('ACC')]
    G_acc = G_simple.subgraph(acc_nodes).copy()

    print(f"Running Louvain on {G_acc.number_of_nodes()} nodes, "
          f"{G_acc.number_of_edges()} edges...")
    partition = community_louvain.best_partition(G_acc, weight='weight',
                                                  random_state=42)

    # Load optional data
    risk_df = None
    if risk_scores_path:
        risk_df = pd.read_csv(risk_scores_path)

    gt_df = None
    mules = set()
    if ground_truth_path:
        gt_df = pd.read_csv(ground_truth_path)
        mules = set(gt_df[gt_df['role'] == 'mule']['account_id'])

    # Build community summaries
    communities = {}
    for node, comm_id in partition.items():
        if comm_id not in communities:
            communities[comm_id] = []
        communities[comm_id].append(node)

    results = []
    for comm_id, members in sorted(communities.items(), key=lambda x: -len(x[1])):
        row = {
            'community_id': comm_id,
            'size': len(members),
            'members': ','.join(sorted(members)),
        }

        # Internal volume (transactions within community)
        internal_vol = 0
        for u in members:
            for v in members:
                if G.has_edge(u, v):
                    for _, data in G[u][v].items():
                        internal_vol += float(data.get('amount', 0))
        row['internal_volume'] = round(internal_vol, 2)

        # Risk scores
        if risk_df is not None:
            member_risks = risk_df[risk_df['account_id'].isin(members)]['risk_score']
            row['avg_risk_score'] = round(member_risks.mean(), 4) if len(member_risks) > 0 else 0
            row['max_risk_score'] = round(member_risks.max(), 4) if len(member_risks) > 0 else 0

        # Ground truth
        if gt_df is not None:
            member_mules = set(members) & mules
            row['mule_count'] = len(member_mules)
            row['mule_fraction'] = round(len(member_mules) / len(members), 4)

        results.append(row)

    results_df = pd.DataFrame(results)

    print(f"\nDetected {len(results_df)} communities")
    print(f"Size range: {results_df['size'].min()} - {results_df['size'].max()}")

    if 'mule_count' in results_df.columns:
        fraud_comms = results_df[results_df['mule_count'] > 0]
        print(f"Communities containing mules: {len(fraud_comms)}")
        print(f"Mules concentrated in {len(fraud_comms)} of {len(results_df)} communities")

    if output_path:
        results_df.to_csv(output_path, index=False)
        print(f"Saved to {output_path}")

    # Also save per-account community assignment
    account_comm = pd.DataFrame([
        {'account_id': node, 'community_id': comm_id}
        for node, comm_id in partition.items()
    ])
    acc_output = output_path.replace('.csv', '_accounts.csv') if output_path else None
    if acc_output:
        account_comm.to_csv(acc_output, index=False)
        print(f"Account assignments saved to {acc_output}")

    return results_df, account_comm


if __name__ == "__main__":
    results, accounts = detect_communities(
        "../data/forensic_network.gpickle",
        risk_scores_path="../data/account_risk_scores.csv",
        ground_truth_path="../data/ground_truth.csv",
        output_path="../data/detected_communities.csv"
    )

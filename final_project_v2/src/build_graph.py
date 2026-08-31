import pandas as pd
import networkx as nx
import pickle

def build_forensic_graph(normalized_csv_path, output_graph_path):
    print("Starting Phase 3: Forensic Graph Construction...")
    df = pd.read_csv(normalized_csv_path)
    initial_row_count = len(df)

    G = nx.MultiDiGraph()

    all_entities = set(df['sender'].unique()).union(set(df['receiver'].unique()))
    for entity in all_entities:
        entity_str = str(entity)
        if entity_str.startswith("AMBIGUOUS") or entity_str.startswith("UNKNOWN"):
            node_type = "quarantined"
        else:
            node_type = "resolved"
        G.add_node(entity_str, node_type=node_type)

    for index, row in df.iterrows():
        sender = str(row['sender'])
        receiver = str(row['receiver'])
        utr = str(row['reference_id'])
        G.add_edge(u_for_edge=sender, v_for_edge=receiver, key=utr,
                   amount=row['amount'], timestamp=row['timestamp'],
                   mode=row['mode'], source_file=row['source'])

    print("\n--- GRAPH CONSTRUCTION AUDIT REPORT ---")
    total_edges = G.number_of_edges()
    print(f"Audit 1: CSV rows={initial_row_count}, Graph edges={total_edges}")
    if total_edges != initial_row_count:
        print("  -> WARNING: MISMATCH")
    else:
        print("  -> SUCCESS")

    total_nodes = G.number_of_nodes()
    quarantined_nodes = sum(1 for n, attr in G.nodes(data=True) if attr.get('node_type') == 'quarantined')
    resolved_nodes = total_nodes - quarantined_nodes
    print(f"Audit 2: total_nodes={total_nodes}, resolved={resolved_nodes}, quarantined={quarantined_nodes}")

    with open(output_graph_path, 'wb') as f:
        pickle.dump(G, f)
    return G, df

if __name__ == "__main__":
    G, df = build_forensic_graph(
        normalized_csv_path="../data/normalized_transactions_v3.csv",
        output_graph_path="../data/forensic_network.gpickle"
    )

    # OUR OWN EXTRA CHECK: did UTR-as-key actually preserve the 11 repeat transactions
    # between ACC00038 and ACC00169 that we found earlier?
    print("\n--- OUR EXTRA CHECK: the 11x repeated pair ---")
    edges_between = G.get_edge_data("ACC00038", "ACC00169")
    if edges_between:
        print(f"Number of distinct parallel edges between ACC00038 -> ACC00169: {len(edges_between)}")
    else:
        print("No edges found between this pair (unexpected).")

    # OUR OWN EXTRA CHECK: any duplicate UTRs that would silently collide as edge keys?
    dupe_utrs = df['reference_id'].duplicated().sum()
    print(f"\nDuplicate UTR values in normalized data (would silently collide as MultiDiGraph keys): {dupe_utrs}")

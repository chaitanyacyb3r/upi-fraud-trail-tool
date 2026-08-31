import networkx as nx
import pandas as pd
import pickle
from datetime import timedelta

def load_graph(graph_path):
    print("Loading Forensic MultiDiGraph...")
    with open(graph_path, 'rb') as f:
        return pickle.load(f)

def build_timestamp_cache(G):
    """Parse every edge's timestamp ONCE, reused by every heuristic below.
    (Fixes a repeated performance bug: scalar pd.to_datetime() inside nested
    loops was catastrophically slow -- up to ~10 minutes for Layering alone.)"""
    for u, v, k, data in G.edges(keys=True, data=True):
        data['parsed_ts'] = pd.to_datetime(data['timestamp'])

def check_fan_in(G, node, min_in_degree=5, max_out_degree=2, lower_pct=0.85, upper_pct=1.05):
    """Verified: 52-54% recall, 0% false positives on both hard-negative and
    normal accounts. This is the primary, trustworthy Tier-1 heuristic."""
    in_edges = list(G.in_edges(node, data=True))
    out_edges = list(G.out_edges(node, data=True))
    if len(in_edges) >= min_in_degree and 0 < len(out_edges) <= max_out_degree:
        total_in = sum(float(d['amount']) for _, _, d in in_edges)
        total_out = sum(float(d['amount']) for _, _, d in out_edges)
        if (total_in * lower_pct) <= total_out <= (total_in * upper_pct):
            explanation = (f"Fan-In: {len(in_edges)} incoming txns totaling Rs{total_in:.2f}, "
                           f"consolidated into {len(out_edges)} outgoing txns totaling Rs{total_out:.2f}.")
            # evidence_path=None for Fan-In: the WHOLE aggregate pattern is the
            # evidence (all in-edges + out-edges), not a specific 2-hop path.
            return [{'account_id': node, 'rule': 'Fan-In', 'explanation': explanation, 'evidence_path': None}]
    return []

def check_layering_chain(G, node, time_window_minutes=200):
    """
    Verified: ~14-28% recall (Hop1/Hop2), ~30-32% false-positive rate on
    normal accounts. Ship as Tier-2 / low-confidence secondary lead only --
    tested at 15min (0% recall, too tight for our own data's 5-180min hop
    delay range) and 24hr (78%+ FP, too loose) -- 200min is the best
    available tradeoff, not a clean solution. Document this honestly.

    evidence_path format: "Sender|UTR|Receiver,Sender|UTR|Receiver"
    Captures the EXACT two transactions that matched (not just the account
    pair) -- fixes a real over-citation bug where multiple unrelated
    transactions between the same two accounts would otherwise all get
    cited as "evidence" for one specific flagged pattern.
    """
    out_edges = list(G.out_edges(node, keys=True, data=True))
    alerts = []
    for _, next_hop, out_utr, out_data in out_edges:
        if G.nodes[next_hop].get('node_type') == 'quarantined':
            continue
        next_hop_outs = list(G.out_edges(next_hop, keys=True, data=True))
        out_amt = float(out_data['amount'])
        out_time = out_data['parsed_ts']
        for _, final_dest, next_out_utr, next_out_data in next_hop_outs:
            next_out_amt = float(next_out_data['amount'])
            next_out_time = next_out_data['parsed_ts']
            if out_time < next_out_time <= out_time + timedelta(minutes=time_window_minutes):
                if (out_amt * 0.85) <= next_out_amt <= (out_amt * 1.05):
                    explanation = (f"Layering: sent Rs{out_amt} to {next_hop}, "
                                   f"forwarded Rs{next_out_amt} to {final_dest}.")
                    path_str = f"{node}|{out_utr}|{next_hop},{next_hop}|{next_out_utr}|{final_dest}"
                    alerts.append({'account_id': node, 'rule': 'Layering (Hop 1)',
                                    'explanation': explanation, 'evidence_path': path_str})
                    alerts.append({'account_id': next_hop, 'rule': 'Layering (Hop 2)',
                                    'explanation': explanation, 'evidence_path': path_str})
    return alerts

def run_heuristics(G):
    print("Executing Detection Heuristics...")
    build_timestamp_cache(G)
    all_alerts = []
    skipped = 0
    for node, attr in G.nodes(data=True):
        # CRITICAL SAFETY NET: never flag based on a merged/ambiguous entity
        if attr.get('node_type') == 'quarantined':
            skipped += 1
            continue
        all_alerts.extend(check_fan_in(G, node))
        all_alerts.extend(check_layering_chain(G, node))
    print(f"(Skipped {skipped} quarantined nodes)")
    df_alerts = pd.DataFrame(all_alerts)
    if not df_alerts.empty:
        df_alerts = df_alerts.drop_duplicates(subset=['account_id', 'rule'])
    print(f"Heuristics complete. Generated {len(df_alerts)} total alerts.")
    return df_alerts

if __name__ == "__main__":
    G = load_graph("../data/forensic_network.gpickle")
    alerts_df = run_heuristics(G)
    alerts_df.to_csv("../data/heuristic_alerts.csv", index=False)
    print("Alerts saved to ../data/heuristic_alerts.csv")
    if not alerts_df.empty:
        print(alerts_df['rule'].value_counts())

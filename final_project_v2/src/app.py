import streamlit as st
import pandas as pd
import networkx as nx
import pickle
from pyvis.network import Network
import streamlit.components.v1 as components
import os

st.set_page_config(page_title="UPI Fraud Trail Investigator", layout="wide")


@st.cache_resource
def load_graph(graph_path):
    with open(graph_path, 'rb') as f:
        return pickle.load(f)


@st.cache_data
def load_alerts(alerts_path):
    return pd.read_csv(alerts_path)


@st.cache_data
def load_csv_safe(path):
    """Load a CSV if it exists, return None otherwise."""
    if os.path.exists(path):
        return pd.read_csv(path)
    return None


def draw_ego_graph(G, target_node, radius=1, evidence_edges=None):
    """Spoke-and-hub ego-graph with evidentiary edges highlighted in yellow
    (Layering) or all edges highlighted red (Fan-In, where the whole
    aggregate pattern is the evidence). Verified: correctly injects the
    2nd-hop node/edge even when it's outside the normal 1-hop radius."""
    ego_subgraph = nx.ego_graph(G, target_node, radius=radius, undirected=True)

    edges_to_remove = [(u, v, k) for u, v, k in ego_subgraph.edges(keys=True)
                       if u != target_node and v != target_node]
    ego_subgraph.remove_edges_from(edges_to_remove)

    if evidence_edges:
        for u, v in evidence_edges:
            if not ego_subgraph.has_node(v) and G.has_node(v):
                ego_subgraph.add_node(v, **G.nodes[v])
            if not ego_subgraph.has_node(u) and G.has_node(u):
                ego_subgraph.add_node(u, **G.nodes[u])
            if not ego_subgraph.has_edge(u, v) and G.has_edge(u, v):
                for k, data in G[u][v].items():
                    ego_subgraph.add_edge(u, v, key=k, **data)

    net = Network(height="600px", width="100%", directed=True, bgcolor="#1e1e1e", font_color="white")
    net.set_options("""
    var options = {
      "edges": { "smooth": { "type": "curvedCW", "roundness": 0.2 } },
      "physics": { "barnesHut": { "gravitationalConstant": -2000, "centralGravity": 0.3, "springLength": 150 } }
    }
    """)

    for node, attr in ego_subgraph.nodes(data=True):
        if node == target_node:
            color, shape, size, title = "#e74c3c", "dot", 25, f"SUSPECT: {node}"
        elif attr.get('node_type') == 'quarantined':
            color, shape, size = "#95a5a6", "box", 15
            title = f"QUARANTINED ENTITY: {node}\nRequires Sec 94 BNSS Notice."
        else:
            color, shape, size, title = "#3498db", "dot", 15, f"RESOLVED: {node}"
        net.add_node(node, label=str(node), title=title, color=color, shape=shape, size=size)

    for u, v, key, data in ego_subgraph.edges(keys=True, data=True):
        amt = data.get('amount', 'N/A')
        time = data.get('timestamp', 'N/A')
        edge_hover = f"UTR: {key}\nAmt: Rs{amt}\nTime: {time}"

        is_evidence = (not evidence_edges) or ((u, v) in evidence_edges)
        if is_evidence:
            edge_color = "#f1c40f" if evidence_edges else "#e74c3c"
            edge_width = 4
        else:
            edge_color = "#424949"
            edge_width = 1

        net.add_edge(u, v, title=edge_hover, value=float(amt), color=edge_color, width=edge_width)

    path = "tmp_graph.html"
    net.save_graph(path)
    with open(path, 'r', encoding='utf-8') as f:
        html_data = f.read()
    return html_data


# ============================================================
# TAB 1: Executive Overview
# ============================================================
def render_overview_tab(G, alerts_df, risk_df, communities_df, benford_df):
    st.header("Executive Overview")

    # KPI row
    col1, col2, col3, col4 = st.columns(4)

    total_accounts = G.number_of_nodes()
    total_edges = G.number_of_edges()

    # Fan-In only alerts (primary detection system)
    fanin_alerts = alerts_df[alerts_df['rule'] == 'Fan-In']
    fanin_count = len(fanin_alerts)

    # Tier 1 risk-scored accounts
    critical_high = 0
    if risk_df is not None:
        critical_high = len(risk_df[risk_df['risk_tier'].isin(['CRITICAL', 'HIGH'])])

    col1.metric("Total Accounts", total_accounts)
    col2.metric("Total Transactions", f"{total_edges:,}")
    col3.metric("Fan-In Alerts", fanin_count)
    col4.metric("High/Critical Risk", critical_high)

    st.markdown("---")

    # Detection system summary
    st.subheader("Detection System Performance")
    st.markdown("""
    | System | Recall | FP-Normal | FP-HardNeg | Precision |
    |--------|--------|-----------|------------|-----------|
    | Fan-In alone | 54.0% (27/50) | 0.0% | 0.0% | 100% |
    | **Fan-In + Tier 1 (recommended)** | **95.8% (46/48)** | **1.7% (8/480)** | **0.0% (0/20)** | **85.2%** |

    *Tier 1 features (out_degree, unique_receivers) validated through two rounds of
    camouflage stress-testing. All metrics on the same 548-account dataset (no holdout).*
    """)

    # Risk tier distribution
    if risk_df is not None:
        st.markdown("---")
        st.subheader("Risk Tier Distribution")
        tier_counts = risk_df['risk_tier'].value_counts().reindex(
            ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'], fill_value=0
        )
        col_a, col_b = st.columns([1, 2])
        with col_a:
            for tier in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
                count = tier_counts.get(tier, 0)
                color_map = {'CRITICAL': '🔴', 'HIGH': '🟠', 'MEDIUM': '🟡', 'LOW': '🟢'}
                st.write(f"{color_map.get(tier, '')} **{tier}**: {count} accounts")
        with col_b:
            st.bar_chart(tier_counts, color="#e74c3c")

    # Community summary
    if communities_df is not None:
        st.markdown("---")
        st.subheader("Fraud Ring Discovery (Louvain Communities)")
        fraud_comms = communities_df[communities_df['mule_fraction'] > 0.3]
        st.success(
            f"**{len(fraud_comms)} fraud-heavy communities detected** "
            f"(>30% mule density) from pure graph structure — zero labels used. "
            f"7 of these correspond exactly to layering chains (A->B->C)."
        )


# ============================================================
# TAB 2: Alert Investigation (original functionality)
# ============================================================
def render_investigation_tab(G, alerts_df, risk_df):
    st.header("Alert Investigation")
    st.caption("Spoke-and-hub view with evidentiary path highlighted. "
               "Unrelated background transactions are dimmed.")

    st.sidebar.header("Investigative Leads")

    # Filter: show Fan-In as primary, Layering as secondary
    show_layering = st.sidebar.checkbox("Show Layering alerts (low-confidence)", value=False)

    if show_layering:
        filtered_alerts = alerts_df
    else:
        filtered_alerts = alerts_df[alerts_df['rule'] == 'Fan-In']

    if len(filtered_alerts) == 0:
        st.warning("No alerts to display. Enable Layering in sidebar to see low-confidence leads.")
        return

    alert_options = []
    for idx, row in filtered_alerts.iterrows():
        tier = "Tier 1" if "Fan-In" in row['rule'] else "Tier 2 (low-conf)"
        # Add risk tier badge if available
        badge = ""
        if risk_df is not None:
            risk_row = risk_df[risk_df['account_id'] == row['account_id']]
            if not risk_row.empty:
                rtier = risk_row.iloc[0]['risk_tier']
                badge = f" [{rtier}]"
        alert_options.append(f"{idx}:: [{tier}] {row['rule']} - {row['account_id']}{badge}")

    selected_alert_str = st.sidebar.selectbox("Select Flagged Event", alert_options)

    if selected_alert_str:
        exact_row_index = int(selected_alert_str.split("::")[0])
        alert_row = alerts_df.loc[exact_row_index]
        selected_account = alert_row['account_id']

        # Parse evidence_path
        evidence_edges = None
        path_str = alert_row.get('evidence_path')
        if pd.notna(path_str) and path_str:
            evidence_edges = []
            for edge_str in str(path_str).split(','):
                parts = edge_str.split('|')
                if len(parts) == 3:
                    evidence_edges.append((parts[0], parts[2]))

        # Risk badge
        risk_info = ""
        if risk_df is not None:
            risk_row = risk_df[risk_df['account_id'] == selected_account]
            if not risk_row.empty:
                score = risk_row.iloc[0]['risk_score']
                rtier = risk_row.iloc[0]['risk_tier']
                risk_info = f" | Risk: {score:.3f} ({rtier})"

        st.subheader(f"Target: {selected_account} | {alert_row['rule']}{risk_info}")

        # Layering warning
        if "Layering" in alert_row['rule']:
            st.warning(
                "**Low-confidence alert.** Layering detection has ~30% false positive "
                "rate and is excluded from the primary detection system. Treat as "
                "investigative lead only, not confirmed fraud."
            )

        st.info(f"**Forensic Explanation:** {alert_row['explanation']}")

        st.markdown("##### 1-Hop Ego Graph (Spoke-and-Hub, Evidence Highlighted)")
        html_graph = draw_ego_graph(G, selected_account, radius=1, evidence_edges=evidence_edges)
        components.html(html_graph, height=620)

        # Risk score breakdown
        if risk_df is not None:
            risk_row = risk_df[risk_df['account_id'] == selected_account]
            if not risk_row.empty:
                r = risk_row.iloc[0]
                st.markdown("##### Risk Score Breakdown (Transparent Formula)")
                c1, c2, c3 = st.columns(3)
                c1.metric("out_degree score", f"{r.get('score_out_degree', 0):.3f}")
                c2.metric("unique_receivers score", f"{r.get('score_unique_receivers', 0):.3f}")
                c3.metric("Combined Risk", f"{r['risk_score']:.3f}", delta=r['risk_tier'])

        st.markdown("---")
        st.markdown("##### Legal Export")

        if st.button("Generate Form 'A' Report (Delhi HC Format)"):
            with st.spinner("Compiling evidentiary UTRs and generating PDF..."):
                from export_report import generate_form_a_pdf

                os.makedirs("../reports", exist_ok=True)
                safe_rule_name = alert_row['rule'].replace(" ", "_").replace("(", "").replace(")", "")
                report_path = f"../reports/FormA_{selected_account}_{safe_rule_name}.pdf"

                generate_form_a_pdf(alert_row, G, report_path)
                st.success(f"Report saved to {report_path}")

                with open(report_path, "rb") as pdf_file:
                    st.download_button(
                        label="Download Form 'A' PDF",
                        data=pdf_file,
                        file_name=os.path.basename(report_path),
                        mime="application/pdf"
                    )


# ============================================================
# TAB 3: Community Map (Fraud Ring Discovery)
# ============================================================
def render_community_tab(communities_df, comm_accounts_df, risk_df):
    st.header("Fraud Ring Discovery (Louvain Community Detection)")
    st.markdown("""
    **Method:** Unsupervised Louvain clustering on the transaction graph — no labels used.
    Communities are groups of accounts that transact heavily with each other.

    **Validated result:** 7 small communities correspond exactly to the layering chains
    (A->B->C mule-to-mule chains) from the fraud rings. Community 4 clusters 7 fan-in
    mules who share overlapping victim pools.
    """)

    if communities_df is None:
        st.error("Community detection data not found. Run `run_enrichment_pipeline.py` first.")
        return

    # Show communities sorted by mule fraction (fraud-heavy first)
    display_df = communities_df[['community_id', 'size', 'mule_count',
                                  'mule_fraction', 'avg_risk_score',
                                  'internal_volume']].copy()
    display_df['mule_pct'] = (display_df['mule_fraction'] * 100).round(1)
    display_df['avg_risk'] = display_df['avg_risk_score'].round(3)
    display_df['volume'] = display_df['internal_volume'].apply(
        lambda x: f"Rs {x:,.0f}"
    )

    st.subheader("All Communities")
    st.dataframe(
        display_df[['community_id', 'size', 'mule_count', 'mule_pct',
                     'avg_risk', 'volume']].sort_values('mule_pct', ascending=False),
        use_container_width=True,
        hide_index=True,
        column_config={
            'community_id': 'Community',
            'size': 'Members',
            'mule_count': 'Mules',
            'mule_pct': st.column_config.NumberColumn('Mule %', format="%.1f%%"),
            'avg_risk': 'Avg Risk Score',
            'volume': 'Internal Volume',
        }
    )

    # Detail view for selected community
    st.markdown("---")
    comm_ids = sorted(communities_df['community_id'].unique())
    selected_comm = st.selectbox(
        "Inspect Community",
        comm_ids,
        format_func=lambda x: f"Community {x} ({int(communities_df[communities_df['community_id']==x]['size'].values[0])} members, "
                               f"{int(communities_df[communities_df['community_id']==x]['mule_count'].values[0])} mules)"
    )

    if selected_comm is not None and comm_accounts_df is not None:
        members = comm_accounts_df[comm_accounts_df['community_id'] == selected_comm]['account_id'].tolist()
        st.write(f"**Members ({len(members)}):** {', '.join(sorted(members))}")

        if risk_df is not None:
            member_risks = risk_df[risk_df['account_id'].isin(members)][
                ['account_id', 'risk_score', 'risk_tier']
            ].sort_values('risk_score', ascending=False)
            st.dataframe(member_risks, use_container_width=True, hide_index=True)


# ============================================================
# TAB 4: Benford's Law (Exploratory)
# ============================================================
def render_benford_tab(benford_df):
    st.header("Benford's Law Analysis")
    st.warning(
        "**Exploratory / Low-Confidence.** With only 15-60 transactions per account, "
        "this test has low statistical power. 43 accounts flagged vs ~26 expected by "
        "chance alone. A null result means 'we can't tell,' not 'no fraud.' "
        "This is supplementary context, not detection evidence."
    )

    if benford_df is None:
        st.error("Benford's data not found. Run `run_enrichment_pipeline.py` first.")
        return

    st.markdown("""
    **What it tests:** Do transaction amounts follow Benford's Law (the natural
    first-digit distribution)? Fabricated amounts sometimes violate this pattern.

    **Performance:** 16% recall, 6% FP-Normal, 18.6% precision — near chance levels.
    """)

    # Summary metrics
    flagged = benford_df[benford_df['benford_flag'] == True]
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Tested", len(benford_df))
    col2.metric("Flagged (p<0.05, n>=20)", len(flagged))
    col3.metric("Too Few Transactions", len(benford_df[benford_df['caveat'] == 'too_few_transactions']))

    # Flagged accounts table
    if len(flagged) > 0:
        st.subheader("Flagged Accounts")
        display = flagged[['account_id', 'n_transactions', 'chi2_statistic',
                           'p_value', 'digit_1_pct', 'digit_2_pct',
                           'digit_3_pct']].sort_values('p_value')
        st.dataframe(display, use_container_width=True, hide_index=True,
                     column_config={
                         'account_id': 'Account',
                         'n_transactions': 'Transactions',
                         'chi2_statistic': 'Chi-square',
                         'p_value': st.column_config.NumberColumn('p-value', format="%.6f"),
                         'digit_1_pct': 'Digit 1 %',
                         'digit_2_pct': 'Digit 2 %',
                         'digit_3_pct': 'Digit 3 %',
                     })

        st.caption("Benford's expected: Digit 1 = 30.1%, Digit 2 = 17.6%, Digit 3 = 12.5%")


# ============================================================
# TAB 5: Risk Scores
# ============================================================
def render_risk_tab(risk_df):
    st.header("Account Risk Scores")
    st.markdown("""
    **Transparent formula:** `risk_score = 0.5 * inv_norm(out_degree) + 0.5 * inv_norm(unique_receivers)`

    Both features measure concentrated outflow (mules send to very few people).
    Equal weights from domain reasoning — NOT fitted to ground truth.
    Validated through two rounds of camouflage stress-testing.
    """)

    if risk_df is None:
        st.error("Risk scores not found. Run `run_enrichment_pipeline.py` first.")
        return

    # Filter by risk tier
    selected_tiers = st.multiselect(
        "Filter by Risk Tier",
        ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'],
        default=['CRITICAL', 'HIGH']
    )

    filtered = risk_df[risk_df['risk_tier'].isin(selected_tiers)]

    display_cols = ['account_id', 'risk_score', 'risk_tier',
                    'score_out_degree', 'score_unique_receivers',
                    'out_degree', 'unique_receivers']
    available = [c for c in display_cols if c in filtered.columns]

    st.dataframe(
        filtered[available].sort_values('risk_score', ascending=False),
        use_container_width=True,
        hide_index=True,
        column_config={
            'account_id': 'Account',
            'risk_score': st.column_config.NumberColumn('Risk Score', format="%.3f"),
            'risk_tier': 'Tier',
            'score_out_degree': st.column_config.NumberColumn('Out-Degree Score', format="%.3f"),
            'score_unique_receivers': st.column_config.NumberColumn('Unique-Recv Score', format="%.3f"),
            'out_degree': 'Out-Degree (raw)',
            'unique_receivers': 'Unique Receivers (raw)',
        }
    )

    st.caption(f"Showing {len(filtered)} of {len(risk_df)} accounts")


# ============================================================
# MAIN
# ============================================================
def main():
    st.title("UPI Fraud Trail Investigator")
    st.markdown("##### Powered by Section 94 BNSS / Section 63 BSA Disclosures")

    try:
        G = load_graph("../data/forensic_network.gpickle")
        alerts_df = load_alerts("../data/heuristic_alerts.csv")
    except FileNotFoundError as e:
        st.error(f"Missing prerequisite files: {e}. Ensure data is in ../data/.")
        return

    # Load Phase B data (optional — dashboard works without it)
    risk_df = load_csv_safe("../data/account_risk_scores.csv")
    communities_df = load_csv_safe("../data/detected_communities.csv")
    comm_accounts_df = load_csv_safe("../data/detected_communities_accounts.csv")
    benford_df = load_csv_safe("../data/benford_results.csv")

    # Tabs — ordered by trust level (most validated first)
    tab_overview, tab_investigate, tab_communities, tab_risk, tab_benford = st.tabs([
        "Overview",
        "Alert Investigation",
        "Fraud Ring Discovery",
        "Risk Scores",
        "Benford's Law (Exploratory)"
    ])

    with tab_overview:
        render_overview_tab(G, alerts_df, risk_df, communities_df, benford_df)

    with tab_investigate:
        render_investigation_tab(G, alerts_df, risk_df)

    with tab_communities:
        render_community_tab(communities_df, comm_accounts_df, risk_df)

    with tab_risk:
        render_risk_tab(risk_df)

    with tab_benford:
        render_benford_tab(benford_df)


if __name__ == "__main__":
    main()

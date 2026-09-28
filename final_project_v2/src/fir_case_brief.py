"""FIR-Ready Case Brief Generator.

Generates a comprehensive First Information Report case brief for a
flagged suspect account, including:
  - Case narrative and modus operandi
  - Complete money trail with amounts and timestamps
  - Organizational hierarchy (victims -> mules -> handlers)
  - Applicable legal sections (BNS, IT Act, PMLA)
  - Recommended investigative actions
  - Evidence summary for court submission

This is SEPARATE from Form 'A' (which is an evidence index).
The FIR brief is a narrative investigation summary that an IO
can use to draft or supplement an FIR.
"""
import pandas as pd
import networkx as nx
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from datetime import datetime
import os


def _compute_account_profile(G, account_id):
    """Compute forensic profile for a single account from the graph."""
    in_edges = list(G.in_edges(account_id, keys=True, data=True))
    out_edges = list(G.out_edges(account_id, keys=True, data=True))

    unique_senders = set(u for u, _, _, _ in in_edges)
    unique_receivers = set(v for _, v, _, _ in out_edges)

    total_in = sum(d.get('amount', 0) for _, _, _, d in in_edges)
    total_out = sum(d.get('amount', 0) for _, _, _, d in out_edges)

    timestamps_in = []
    timestamps_out = []
    for u, v, k, d in in_edges:
        try:
            timestamps_in.append(pd.to_datetime(d.get('timestamp', '')))
        except Exception:
            pass
    for u, v, k, d in out_edges:
        try:
            timestamps_out.append(pd.to_datetime(d.get('timestamp', '')))
        except Exception:
            pass

    first_txn = min(timestamps_in + timestamps_out) if (timestamps_in or timestamps_out) else None
    last_txn = max(timestamps_in + timestamps_out) if (timestamps_in or timestamps_out) else None

    flow_ratio = total_out / total_in if total_in > 0 else 0

    return {
        'account_id': account_id,
        'unique_senders': len(unique_senders),
        'unique_receivers': len(unique_receivers),
        'total_incoming': total_in,
        'total_outgoing': total_out,
        'flow_ratio': flow_ratio,
        'in_txn_count': len(in_edges),
        'out_txn_count': len(out_edges),
        'first_txn': first_txn,
        'last_txn': last_txn,
        'senders': sorted(unique_senders),
        'receivers': sorted(unique_receivers),
    }


def _classify_fraud_pattern(alert_row, profile):
    """Classify the fraud pattern and generate MO description."""
    rule = alert_row['rule']

    if 'Fan-In' in rule:
        pattern = "Fan-In Collector (Aggregation Fraud)"
        mo = (
            f"The suspect account {profile['account_id']} operated as a "
            f"fund aggregation node, receiving deposits from "
            f"{profile['unique_senders']} unique source accounts totalling "
            f"Rs {profile['total_incoming']:,.2f}. "
            f"Approximately {profile['flow_ratio']*100:.0f}% of incoming funds "
            f"(Rs {profile['total_outgoing']:,.2f}) were rapidly forwarded to "
            f"{profile['unique_receivers']} downstream account(s), consistent "
            f"with the modus operandi of a mule/collector account in a "
            f"UPI/IMPS fraud syndicate. The high fan-in ratio "
            f"({profile['unique_senders']} senders : {profile['unique_receivers']} "
            f"receivers) is a strong structural indicator of fund aggregation "
            f"for onward laundering."
        )
    elif 'Layering' in rule:
        pattern = "Layering / Rapid Pass-Through"
        mo = (
            f"The suspect account {profile['account_id']} participated in a "
            f"multi-hop layering chain, receiving funds and rapidly forwarding "
            f"them to the next account in the chain. Total throughput: "
            f"Rs {profile['total_incoming']:,.2f} in, "
            f"Rs {profile['total_outgoing']:,.2f} out "
            f"({profile['flow_ratio']*100:.0f}% pass-through rate). "
            f"This pattern is consistent with structuring/layering under "
            f"PMLA 2002, designed to obscure the audit trail between the "
            f"victim and the ultimate beneficiary."
        )
    else:
        pattern = "Suspicious Transaction Pattern"
        mo = f"Account {profile['account_id']} flagged for anomalous transaction behavior."

    return pattern, mo


def _get_legal_sections(pattern_type):
    """Return applicable legal sections based on fraud pattern."""
    sections = [
        {
            'section': 'Section 318 BNS',
            'title': 'Cheating',
            'applicability': 'Primary offence -- victims were induced to transfer funds under false pretences.'
        },
        {
            'section': 'Section 319 BNS',
            'title': 'Cheating by Personation',
            'applicability': 'If accused impersonated bank officials, delivery agents, or other trusted entities.'
        },
        {
            'section': 'Section 316(2) BNS',
            'title': 'Criminal Breach of Trust',
            'applicability': 'Mule account holder entrusted with funds, dishonestly misappropriated them.'
        },
        {
            'section': 'Section 61(2) BNS',
            'title': 'Criminal Conspiracy',
            'applicability': 'Coordinated operation involving multiple mule accounts indicates conspiracy.'
        },
        {
            'section': 'Section 66C IT Act 2000',
            'title': 'Identity Theft',
            'applicability': 'If UPI credentials, OTPs, or identity documents were fraudulently obtained.'
        },
        {
            'section': 'Section 66D IT Act 2000',
            'title': 'Cheating by Personation using Computer Resource',
            'applicability': 'Use of digital payment systems (UPI/IMPS/NEFT) to perpetrate the fraud.'
        },
        {
            'section': 'Section 3/4 PMLA 2002',
            'title': 'Money Laundering',
            'applicability': 'Multi-hop fund transfers designed to obscure proceeds of crime.'
        },
    ]

    if 'Layering' in pattern_type:
        sections.append({
            'section': 'Section 5 PMLA 2002',
            'title': 'Attachment of Property',
            'applicability': 'Layered fund movement warrants provisional attachment of accounts in the chain.'
        })

    return sections


def _get_recommended_actions(profile, pattern_type):
    """Generate recommended investigative actions."""
    actions = [
        {
            'priority': 'IMMEDIATE',
            'action': 'Account Freeze / Lien',
            'detail': (
                f"Issue directions to the bank holding account {profile['account_id']} "
                f"to place an immediate lien/freeze under Section 102 BNSS. "
                f"Current suspected proceeds: Rs {profile['total_incoming']:,.2f}."
            )
        },
        {
            'priority': 'IMMEDIATE',
            'action': 'Section 94 BNSS Notice to Banks',
            'detail': (
                f"Issue production orders to banks holding the following accounts "
                f"for complete KYC records, statement of accounts, IP login logs, "
                f"and device binding details: {profile['account_id']}"
                + (f", {', '.join(profile['receivers'][:5])}" if profile['receivers'] else "")
                + "."
            )
        },
        {
            'priority': 'IMMEDIATE',
            'action': 'UPI Service Provider Notice',
            'detail': (
                "Issue notice to NPCI / UPI PSP (PhonePe/GPay/Paytm) under Section 94 BNSS "
                "for transaction metadata, device fingerprints, IP addresses, and "
                "merchant verification status for the flagged accounts."
            )
        },
        {
            'priority': 'HIGH',
            'action': 'CDR/IPDR Requisition',
            'detail': (
                "Requisition Call Detail Records (CDR) and IP Detail Records (IPDR) "
                "from telecom operators for mobile numbers linked to the suspect account(s) "
                "to establish location and communication patterns during the fraud window."
            )
        },
        {
            'priority': 'HIGH',
            'action': 'FIU-IND Suspicious Transaction Report',
            'detail': (
                f"File STR with Financial Intelligence Unit-India (FIU-IND) citing "
                f"Rs {profile['total_incoming']:,.2f} in suspected proceeds across "
                f"{profile['in_txn_count']} transactions from {profile['unique_senders']} sources."
            )
        },
    ]

    if profile['unique_senders'] > 5:
        actions.append({
            'priority': 'HIGH',
            'action': 'Victim Identification & Statements',
            'detail': (
                f"Contact the {profile['unique_senders']} source accounts "
                f"(potential victims) to record statements under Section 180 BNSS. "
                f"Cross-reference with existing cybercrime complaints on the "
                f"National Cybercrime Reporting Portal (cybercrime.gov.in)."
            )
        })

    if 'Layering' in pattern_type:
        actions.append({
            'priority': 'HIGH',
            'action': 'Downstream Account Tracing',
            'detail': (
                f"Trace all downstream recipients ({', '.join(profile['receivers'][:5])}) "
                f"for further layering. Each hop account requires the same freeze + "
                f"KYC + CDR treatment. Coordinate with jurisdictional PS if accounts "
                f"are in different states."
            )
        })

    actions.append({
        'priority': 'STANDARD',
        'action': 'Inter-State Coordination (if applicable)',
        'detail': (
            "If suspect accounts are registered in different states, initiate "
            "coordination through I4C (Indian Cyber Crime Coordination Centre) "
            "and issue LRs to concerned State Cyber Cells."
        )
    })

    actions.append({
        'priority': 'STANDARD',
        'action': 'Digital Evidence Preservation',
        'detail': (
            "Ensure all digital evidence (transaction logs, IP records, device data) "
            "is preserved with proper chain of custody and certified under "
            "Section 63(4) Bharatiya Sakshya Adhiniyam before being presented in court."
        )
    })

    return actions


def generate_fir_brief_pdf(alert_row, G, output_filepath, risk_df=None, comm_df=None):
    """Generate a comprehensive FIR-ready case brief PDF.

    Args:
        alert_row: Row from heuristic_alerts.csv
        G: NetworkX MultiDiGraph
        output_filepath: Where to save the PDF
        risk_df: Optional account_risk_scores.csv DataFrame
        comm_df: Optional detected_communities_accounts.csv DataFrame

    Returns:
        Path to generated PDF
    """
    doc = SimpleDocTemplate(
        output_filepath, pagesize=A4,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
        leftMargin=2*cm, rightMargin=2*cm
    )
    styles = getSampleStyleSheet()
    story = []

    # Custom styles
    title_style = ParagraphStyle(
        'FIRTitle', parent=styles['Heading1'],
        fontSize=16, alignment=TA_CENTER,
        spaceAfter=6, textColor=colors.HexColor("#1a1a1a")
    )
    subtitle_style = ParagraphStyle(
        'FIRSubtitle', parent=styles['Normal'],
        fontSize=10, alignment=TA_CENTER,
        textColor=colors.HexColor("#555555"), spaceAfter=20
    )
    section_style = ParagraphStyle(
        'SectionHead', parent=styles['Heading2'],
        fontSize=12, spaceBefore=16, spaceAfter=8,
        textColor=colors.HexColor("#1b3a6b"),
        borderWidth=0, borderPadding=0
    )
    body_style = ParagraphStyle(
        'BodyText2', parent=styles['Normal'],
        fontSize=9.5, leading=13, alignment=TA_JUSTIFY, spaceAfter=6
    )
    small_style = ParagraphStyle(
        'SmallText', parent=styles['Normal'],
        fontSize=8, leading=10, textColor=colors.HexColor("#555555")
    )

    account_id = alert_row['account_id']
    profile = _compute_account_profile(G, account_id)
    pattern_type, mo_description = _classify_fraud_pattern(alert_row, profile)

    # ---- HEADER ----
    story.append(Paragraph("FIR-READY CASE BRIEF", title_style))
    story.append(Paragraph("Cyber Financial Fraud Investigation", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1b3a6b")))
    story.append(Spacer(1, 12))

    # ---- CASE METADATA ----
    now = datetime.now()
    meta_data = [
        ["Case Reference", f"CF/{now.strftime('%Y')}/{account_id[-3:]}"],
        ["Date of Brief", now.strftime("%d %B %Y, %I:%M %p")],
        ["Suspect Account", account_id],
        ["Detection Rule", alert_row['rule']],
        ["Fraud Pattern", pattern_type],
        ["Activity Window",
         f"{profile['first_txn'].strftime('%d %b %Y') if profile['first_txn'] else 'N/A'} -- "
         f"{profile['last_txn'].strftime('%d %b %Y') if profile['last_txn'] else 'N/A'}"],
    ]

    # Add risk score if available
    if risk_df is not None:
        risk_row = risk_df[risk_df['account_id'] == account_id]
        if not risk_row.empty:
            score = risk_row.iloc[0]['risk_score']
            tier = risk_row.iloc[0]['risk_tier']
            meta_data.append(["Risk Score", f"{score:.3f} ({tier})"])

    # Add community if available
    if comm_df is not None:
        comm_row = comm_df[comm_df['account_id'] == account_id]
        if not comm_row.empty:
            cid = int(comm_row.iloc[0]['community_id'])
            meta_data.append(["Fraud Cluster", f"Community {cid}"])

    meta_table = Table(meta_data, colWidths=[130, 340])
    meta_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor("#1b3a6b")),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 16))

    # ---- SECTION 1: MODUS OPERANDI ----
    story.append(Paragraph("1. MODUS OPERANDI", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 4))
    story.append(Paragraph(mo_description, body_style))

    # ---- SECTION 2: FINANCIAL SUMMARY ----
    story.append(Paragraph("2. FINANCIAL SUMMARY", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 4))

    fin_data = [
        ["Metric", "Value"],
        ["Total Incoming Funds", f"Rs {profile['total_incoming']:,.2f}"],
        ["Total Outgoing Funds", f"Rs {profile['total_outgoing']:,.2f}"],
        ["Pass-Through Rate", f"{profile['flow_ratio']*100:.1f}%"],
        ["Incoming Transactions", str(profile['in_txn_count'])],
        ["Outgoing Transactions", str(profile['out_txn_count'])],
        ["Unique Source Accounts (potential victims)", str(profile['unique_senders'])],
        ["Unique Destination Accounts", str(profile['unique_receivers'])],
    ]

    fin_table = Table(fin_data, colWidths=[250, 220])
    fin_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1b3a6b")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#f8f9f9")),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(fin_table)
    story.append(Spacer(1, 8))

    # ---- SECTION 3: ORGANIZATIONAL HIERARCHY ----
    story.append(Paragraph("3. ORGANIZATIONAL HIERARCHY (Fund Flow Map)", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 4))

    if 'Fan-In' in alert_row['rule']:
        hierarchy_text = (
            f"<b>Victims / Source Accounts ({profile['unique_senders']}):</b> "
            f"{', '.join(profile['senders'][:10])}"
            + (f" ... and {profile['unique_senders']-10} more" if profile['unique_senders'] > 10 else "")
            + f"<br/><br/>"
            f"<b>Mule / Collector Account:</b> {account_id}<br/><br/>"
            f"<b>Handler / Cashout Account(s) ({profile['unique_receivers']}):</b> "
            f"{', '.join(profile['receivers'])}"
        )
    else:
        hierarchy_text = (
            f"<b>Upstream (money received from):</b> "
            f"{', '.join(profile['senders'][:10])}<br/><br/>"
            f"<b>Current Hop (suspect):</b> {account_id}<br/><br/>"
            f"<b>Downstream (money forwarded to):</b> "
            f"{', '.join(profile['receivers'][:10])}"
        )

    story.append(Paragraph(hierarchy_text, body_style))
    story.append(Spacer(1, 8))

    # ---- SECTION 4: KEY TRANSACTIONS (Top 15) ----
    story.append(Paragraph("4. KEY EVIDENTIARY TRANSACTIONS", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 4))

    # Get all evidence transactions
    from export_report import extract_evidence_data
    evidence = extract_evidence_data(G, alert_row)

    if evidence:
        # Show top transactions by amount
        evidence_sorted = sorted(evidence, key=lambda x: x['amount'], reverse=True)[:15]

        txn_data = [["#", "UTR", "From", "To", "Amount (Rs)", "Timestamp"]]
        for idx, item in enumerate(evidence_sorted, 1):
            txn_data.append([
                str(idx),
                str(item['utr'])[:12],
                str(item['sender']),
                str(item['receiver']),
                f"{item['amount']:,.2f}",
                str(item['timestamp'])
            ])

        txn_table = Table(txn_data, colWidths=[25, 85, 70, 70, 80, 140])
        txn_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7.5),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (4, 1), (4, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#f8f9f9")),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(txn_table)

        if len(evidence) > 15:
            story.append(Paragraph(
                f"<i>Showing top 15 of {len(evidence)} transactions by amount. "
                f"Complete evidence index available in Form 'A' report.</i>",
                small_style
            ))
    else:
        story.append(Paragraph("<i>No transactions found in graph for this account.</i>", body_style))

    # ---- PAGE BREAK ----
    story.append(PageBreak())

    # ---- SECTION 5: APPLICABLE LEGAL SECTIONS ----
    story.append(Paragraph("5. APPLICABLE LEGAL PROVISIONS", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 4))

    legal_sections = _get_legal_sections(pattern_type)
    legal_data = [["Section", "Title", "Applicability"]]
    for s in legal_sections:
        legal_data.append([s['section'], s['title'], s['applicability']])

    legal_table = Table(legal_data, colWidths=[100, 100, 270])
    legal_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1b3a6b")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#f8f9f9")),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(legal_table)
    story.append(Spacer(1, 12))

    # ---- SECTION 6: RECOMMENDED ACTIONS ----
    story.append(Paragraph("6. RECOMMENDED INVESTIGATIVE ACTIONS", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 4))

    actions = _get_recommended_actions(profile, pattern_type)

    for i, act in enumerate(actions, 1):
        priority_color = {
            'IMMEDIATE': '#e74c3c',
            'HIGH': '#f39c12',
            'STANDARD': '#3498db'
        }.get(act['priority'], '#555555')

        story.append(Paragraph(
            f"<b>{i}. [{act['priority']}] {act['action']}</b>",
            ParagraphStyle('ActionHead', parent=body_style,
                          textColor=colors.HexColor(priority_color),
                          fontSize=10, spaceAfter=2)
        ))
        story.append(Paragraph(act['detail'], body_style))
        story.append(Spacer(1, 4))

    # ---- SECTION 7: DISCLAIMER & CERTIFICATION ----
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1b3a6b")))
    story.append(Spacer(1, 8))

    disclaimer = (
        "This case brief is auto-generated by the UPI Fraud Trail Investigator "
        "based on algorithmic analysis of transaction patterns. It is intended as "
        "an investigative aid for the Investigating Officer and does not constitute "
        "a final legal opinion. All facts, account details, and transaction records "
        "must be independently verified before inclusion in the FIR. "
        "Electronic evidence cited herein requires certification under Section 63(4) "
        "of the Bharatiya Sakshya Adhiniyam (BSA) from the respective Nodal Officers "
        "of the reporting financial institutions."
    )
    story.append(Paragraph(f"<i>{disclaimer}</i>", small_style))
    story.append(Spacer(1, 20))

    # Signature block
    sig_data = [
        ["", ""],
        ["_________________________", "_________________________"],
        ["Investigating Officer", "Reviewing Officer"],
        ["Name:", "Name:"],
        ["Designation:", "Designation:"],
        ["Date:", "Date:"],
    ]
    sig_table = Table(sig_data, colWidths=[235, 235])
    sig_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(sig_table)

    doc.build(story)
    return output_filepath

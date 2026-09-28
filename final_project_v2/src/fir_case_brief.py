"""FIR-Ready Case Brief Generator with Graphical SOP Action Flowchart.

Generates a comprehensive First Information Report case brief for a
flagged suspect account, including:
  - Case narrative and modus operandi
  - Complete money trail with amounts and timestamps
  - Organizational hierarchy (victims -> mules -> handlers)
  - Applicable legal sections (BNS, IT Act, PMLA)
  - Graphical flowchart diagram of recommended investigative actions
  - Step-by-step actionable directives with color-coded priority
  - Court-admissible evidence summary with IO/RO sign-off blocks
"""
import os
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.patches as patches

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from datetime import datetime


def generate_action_flowchart_image(output_path):
    """Generate a clean, high-resolution 3-stage investigative SOP flowchart."""
    fig, ax = plt.subplots(figsize=(10.5, 4.9), dpi=300)
    fig.patch.set_facecolor('#FFFFFF')
    ax.set_facecolor('#FFFFFF')
    ax.axis('off')
    ax.set_xlim(0, 102)
    ax.set_ylim(0, 100)

    # Title / Header
    ax.text(51, 96.5, "CYBER FINANCIAL FRAUD INVESTIGATIVE ACTION LIFECYCLE (SOP)",
            ha='center', va='center', fontsize=11.5, fontweight='bold', color='#1B3A6B')
    ax.text(51, 92, "Sequential Action Protocol: Emergency Freeze -> Evidence Gathering -> Legal Prosecution",
            ha='center', va='center', fontsize=8, fontstyle='italic', color='#555555')

    phases = [
        {
            "stage_badge": "STAGE 1",
            "title": "IMMEDIATE CONTAINMENT",
            "subtitle": "0 - 24 Hours | High Urgency",
            "color": "#C62828",       # Crimson Red
            "bg_color": "#FFEBEE",    # Soft red tint
            "border": "#E57373",
            "x": 2, "w": 27,
            "steps": [
                ("1. Sec 102 BNSS A/C Freeze", "Issue urgent lien on suspect account to prevent immediate ATM cashout."),
                ("2. Sec 94 BNSS Bank Order", "Requisition full KYC, detailed statements, and IP login logs."),
                ("3. UPI / PSP Nodal Notice", "Obtain device binding, MAC/IMEI, and VPA transaction records.")
            ]
        },
        {
            "stage_badge": "STAGE 2",
            "title": "TRAIL & EVIDENCE EXPANSION",
            "subtitle": "24 - 72 Hours | Forensic Tracing",
            "color": "#EF6C00",       # Deep Amber/Orange
            "bg_color": "#FFF3E0",    # Soft orange tint
            "border": "#FFB74D",
            "x": 37.5, "w": 27,
            "steps": [
                ("4. Telecom CDR / IPDR Notice", "Track linked mobile geolocation and internet session logs during fraud window."),
                ("5. FIU-IND STR Portal Filing", "Submit Suspicious Transaction Report to FIU-IND for AML tracking."),
                ("6. Victim Verification (Sec 180)", "Cross-verify 1930 NCRP complaint tickets & record victim statements.")
            ]
        },
        {
            "stage_badge": "STAGE 3",
            "title": "PROSECUTION & PACKAGING",
            "subtitle": "72h+ | Judicial Admissibility",
            "color": "#1565C0",       # Navy Blue
            "bg_color": "#E3F2FD",    # Soft blue tint
            "border": "#64B5F6",
            "x": 73, "w": 27,
            "steps": [
                ("7. Downstream Cascade Freezes", "Trace hop-2/3 mules & issue secondary liens via I4C portal."),
                ("8. Sec 63(4) BSA Certification", "Obtain Nodal Officer digital certificates for all electronic records."),
                ("9. Court FIR & Form 'A' Filing", "Submit completed case brief & Form 'A' evidence index to Magistrate.")
            ]
        }
    ]

    for p in phases:
        # Phase Header Banner
        header_box = patches.FancyBboxPatch(
            (p['x'], 78), p['w'], 10.5,
            boxstyle="round,pad=0.6,rounding_size=2",
            facecolor=p['color'], edgecolor='none', lw=0
        )
        ax.add_patch(header_box)
        
        # Stage pill
        ax.text(p['x'] + p['w']/2, 85.5, p['stage_badge'], ha='center', va='center',
                fontsize=7.0, fontweight='heavy', color='#FFFFFF', alpha=0.85)
        ax.text(p['x'] + p['w']/2, 82.2, p['title'], ha='center', va='center',
                fontsize=8.0, fontweight='bold', color='#FFFFFF')
        ax.text(p['x'] + p['w']/2, 79.2, p['subtitle'], ha='center', va='center',
                fontsize=6.5, fontstyle='italic', color='#FFFFFF', alpha=0.9)

        # Background Container for steps
        container = patches.FancyBboxPatch(
            (p['x'], 5), p['w'], 71,
            boxstyle="round,pad=0.6,rounding_size=2",
            facecolor=p['bg_color'], edgecolor=p['border'], lw=1.2, ls='--'
        )
        ax.add_patch(container)

        # Steps inside each phase
        y_pos = 68.5
        for idx, (head, desc) in enumerate(p['steps']):
            step_card = patches.FancyBboxPatch(
                (p['x'] + 1.2, y_pos - 16.5), p['w'] - 2.4, 18,
                boxstyle="round,pad=0.5,rounding_size=1.5",
                facecolor='#FFFFFF', edgecolor=p['border'], lw=1.0
            )
            ax.add_patch(step_card)

            # Step title badge
            ax.text(p['x'] + 2.2, y_pos - 2.5, head, ha='left', va='top',
                    fontsize=7.4, fontweight='bold', color=p['color'])
            
            # Step description wrapped
            words = desc.split()
            lines = []
            curr = []
            for w in words:
                curr.append(w)
                if len(" ".join(curr)) > 27:
                    lines.append(" ".join(curr))
                    curr = []
            if curr:
                lines.append(" ".join(curr))
            
            wrapped_text = "\n".join(lines[:3])
            ax.text(p['x'] + 2.2, y_pos - 7.5, wrapped_text, ha='left', va='top',
                    fontsize=6.5, color='#333333', linespacing=1.25)

            # Connector arrow down within column
            if idx < len(p['steps']) - 1:
                ax.annotate(
                    '', xy=(p['x'] + p['w']/2, y_pos - 19.2),
                    xytext=(p['x'] + p['w']/2, y_pos - 17.0),
                    arrowprops=dict(arrowstyle="->", color=p['color'], lw=1.6)
                )

            y_pos -= 23.5

    # Connecting horizontal arrows between phases in the gap
    # Gap 1: 29 to 37.5 -> arrow from 30.5 to 36.5
    ax.annotate(
        '', xy=(36.5, 83.2), xytext=(30.5, 83.2),
        arrowprops=dict(arrowstyle="->", color='#333333', lw=2.0, mutation_scale=12)
    )
    ax.text(33.5, 86.2, "ESCALATE", ha='center', va='center', fontsize=6.5, fontweight='bold', color='#444444')

    # Gap 2: 64.5 to 73 -> arrow from 66 to 72
    ax.annotate(
        '', xy=(72.0, 83.2), xytext=(66.0, 83.2),
        arrowprops=dict(arrowstyle="->", color='#333333', lw=2.0, mutation_scale=12)
    )
    ax.text(69.0, 86.2, "PROSECUTE", ha='center', va='center', fontsize=6.5, fontweight='bold', color='#444444')

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='#FFFFFF')
    plt.close()
    return output_path


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
            'title': 'Cheating by Personation via Computer',
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
            'action': 'Section 102 BNSS Account Freeze / Lien',
            'detail': (
                f"Issue immediate direction to the reporting bank for account {profile['account_id']} "
                f"to place a full debit freeze under Section 102 BNSS. "
                f"Suspected fraudulent throughput: Rs {profile['total_incoming']:,.2f}."
            )
        },
        {
            'priority': 'IMMEDIATE',
            'action': 'Section 94 BNSS Production Order to Bank',
            'detail': (
                f"Issue formal production order to branch nodal officer for complete account opening KYC "
                f"(Aadhaar/PAN), verified linked mobile number, transaction ledger, and IP access logs."
            )
        },
        {
            'priority': 'IMMEDIATE',
            'action': 'UPI Payment Service Provider (PSP) Notice',
            'detail': (
                "Requisition device binding history, MAC address, IMEI, registered UPI VPAs, and SIM "
                "switch timestamps from NPCI and the concerned Third Party App Provider (TPAP)."
            )
        },
        {
            'priority': 'HIGH',
            'action': 'Telecom CDR & IPDR Data Requisition',
            'detail': (
                "Issue requisition to telecom service providers for Call Detail Records (CDR) and "
                "IP Detail Records (IPDR) of linked mobile numbers to establish physical cell tower locations."
            )
        },
        {
            'priority': 'HIGH',
            'action': 'FIU-IND Suspicious Transaction Report (STR)',
            'detail': (
                f"Lodge formal STR with Financial Intelligence Unit-India citing Rs {profile['total_incoming']:,.2f} "
                f"across {profile['in_txn_count']} transactions from {profile['unique_senders']} sources."
            )
        },
        {
            'priority': 'HIGH',
            'action': 'Victim Statement Recording (Sec 180 BNSS)',
            'detail': (
                f"Contact the {profile['unique_senders']} source accounts to verify fraud reports and "
                f"cross-reference National Cybercrime Reporting Portal (1930 NCRP) acknowledgement numbers."
            )
        },
        {
            'priority': 'STANDARD',
            'action': 'Downstream Mule Tracing & Secondary Freezes',
            'detail': (
                f"Cascade Section 102 BNSS freezes to downstream recipient accounts ({', '.join(profile['receivers'][:5])}) "
                f"to prevent cashout at final ATM endpoints."
            )
        },
        {
            'priority': 'STANDARD',
            'action': 'Digital Evidence Certification (Sec 63(4) BSA)',
            'detail': (
                "Obtain mandatory Section 63(4) Bharatiya Sakshya Adhiniyam certificates from Nodal "
                "Officers of banks and telecom providers to ensure court admissibility of electronic records."
            )
        },
    ]

    return actions


def generate_fir_brief_pdf(alert_row, G, output_filepath, risk_df=None, comm_df=None):
    """Generate a comprehensive 4-page FIR-ready case brief PDF with SOP flowchart."""
    doc = SimpleDocTemplate(
        output_filepath, pagesize=A4,
        topMargin=1.2*cm, bottomMargin=1.2*cm,
        leftMargin=1.8*cm, rightMargin=1.8*cm
    )
    styles = getSampleStyleSheet()
    story = []

    # Custom styles
    title_style = ParagraphStyle(
        'FIRTitle', parent=styles['Heading1'],
        fontSize=15, alignment=TA_CENTER,
        spaceAfter=4, textColor=colors.HexColor("#1b3a6b")
    )
    subtitle_style = ParagraphStyle(
        'FIRSubtitle', parent=styles['Normal'],
        fontSize=9.5, alignment=TA_CENTER,
        textColor=colors.HexColor("#555555"), spaceAfter=14
    )
    section_style = ParagraphStyle(
        'SectionHead', parent=styles['Heading2'],
        fontSize=11, spaceBefore=12, spaceAfter=6,
        textColor=colors.HexColor("#1b3a6b")
    )
    body_style = ParagraphStyle(
        'BodyText2', parent=styles['Normal'],
        fontSize=8.5, leading=12, alignment=TA_JUSTIFY, spaceAfter=5
    )
    cell_bold_style = ParagraphStyle(
        'CellBold', parent=styles['Normal'],
        fontSize=7.5, leading=9.5, textColor=colors.HexColor("#1a1a1a"), fontName='Helvetica-Bold'
    )
    cell_text_style = ParagraphStyle(
        'CellText', parent=styles['Normal'],
        fontSize=7.5, leading=9.5, textColor=colors.HexColor("#2C3E50")
    )
    cell_header_style = ParagraphStyle(
        'CellHeader', parent=styles['Normal'],
        fontSize=8, leading=10, textColor=colors.whitesmoke, fontName='Helvetica-Bold'
    )
    small_style = ParagraphStyle(
        'SmallText', parent=styles['Normal'],
        fontSize=7.5, leading=10, textColor=colors.HexColor("#555555")
    )

    account_id = alert_row['account_id']
    profile = _compute_account_profile(G, account_id)
    pattern_type, mo_description = _classify_fraud_pattern(alert_row, profile)

    # ============================================================
    # PAGE 1: CASE OVERVIEW, MO, FINANCIALS, ORG HIERARCHY
    # ============================================================
    story.append(Paragraph("FIRST INFORMATION REPORT (FIR) - CASE BRIEF", title_style))
    story.append(Paragraph("Cybercrime Financial Investigation & Evidence Summary", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1b3a6b")))
    story.append(Spacer(1, 8))

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

    if risk_df is not None:
        risk_row = risk_df[risk_df['account_id'] == account_id]
        if not risk_row.empty:
            score = risk_row.iloc[0]['risk_score']
            tier = risk_row.iloc[0]['risk_tier']
            meta_data.append(["Risk Score", f"{score:.3f} ({tier})"])

    if comm_df is not None:
        comm_row = comm_df[comm_df['account_id'] == account_id]
        if not comm_row.empty:
            cid = int(comm_row.iloc[0]['community_id'])
            meta_data.append(["Fraud Cluster", f"Community {cid} (Louvain Unsupervised)"])

    meta_table = Table(meta_data, colWidths=[120, 360])
    meta_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor("#1b3a6b")),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 8))

    # Section 1: Modus Operandi
    story.append(Paragraph("1. MODUS OPERANDI & NARRATIVE", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 4))
    story.append(Paragraph(mo_description, body_style))
    story.append(Spacer(1, 6))

    # Section 2: Financial Summary
    story.append(Paragraph("2. FINANCIAL SUMMARY & FLOW RATIOS", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 4))

    fin_data = [
        ["Metric Description", "Quantified Value"],
        ["Total Incoming Funds Deposited", f"Rs {profile['total_incoming']:,.2f}"],
        ["Total Outgoing Funds Dispersed", f"Rs {profile['total_outgoing']:,.2f}"],
        ["Fund Pass-Through Velocity Ratio", f"{profile['flow_ratio']*100:.1f}% forwarded"],
        ["Inflow Transaction Count", f"{profile['in_txn_count']} transactions"],
        ["Outflow Transaction Count", f"{profile['out_txn_count']} transactions"],
        ["Unique Source Accounts (Potential Victims)", f"{profile['unique_senders']} accounts"],
        ["Unique Destination Accounts (Handlers/Mules)", f"{profile['unique_receivers']} accounts"],
    ]

    fin_table = Table(fin_data, colWidths=[270, 210])
    fin_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1b3a6b")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#f8f9f9")),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(fin_table)
    story.append(Spacer(1, 8))

    # Section 3: Organizational Hierarchy
    story.append(Paragraph("3. NETWORK ENTITY HIERARCHY (Fund Flow Map)", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 4))

    if 'Fan-In' in alert_row['rule']:
        hierarchy_text = (
            f"<b>Source Accounts / Victims ({profile['unique_senders']}):</b> "
            f"{', '.join(profile['senders'][:12])}"
            + (f" ... and {profile['unique_senders']-12} more" if profile['unique_senders'] > 12 else "")
            + f"<br/><br/>"
            f"<b>Mule / Aggregator Account:</b> {account_id}<br/><br/>"
            f"<b>Immediate Handler / Cashout Account(s) ({profile['unique_receivers']}):</b> "
            f"{', '.join(profile['receivers'])}"
        )
    else:
        hierarchy_text = (
            f"<b>Upstream Accounts (Inflow sources):</b> "
            f"{', '.join(profile['senders'][:10])}<br/><br/>"
            f"<b>Current Node (Suspect In-Chain):</b> {account_id}<br/><br/>"
            f"<b>Downstream Accounts (Next hops):</b> "
            f"{', '.join(profile['receivers'][:10])}"
        )

    story.append(Paragraph(hierarchy_text, body_style))

    # ============================================================
    # PAGE 2: KEY EVIDENTIARY TRANSACTIONS
    # ============================================================
    story.append(PageBreak())
    story.append(Paragraph("4. KEY EVIDENTIARY TRANSACTIONS (UTR Audit Trail)", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 4))

    from export_report import extract_evidence_data
    evidence = extract_evidence_data(G, alert_row)

    if evidence:
        evidence_sorted = sorted(evidence, key=lambda x: x['amount'], reverse=True)[:18]
        txn_data = [["#", "12-Digit UTR", "Origin Account", "Beneficiary", "Amount (Rs)", "Recorded Timestamp"]]
        for idx, item in enumerate(evidence_sorted, 1):
            txn_data.append([
                str(idx),
                str(item['utr'])[:12],
                str(item['sender']),
                str(item['receiver']),
                f"{item['amount']:,.2f}",
                str(item['timestamp'])
            ])

        txn_table = Table(txn_data, colWidths=[22, 85, 75, 75, 75, 148])
        txn_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7.5),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (4, 1), (4, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#f8f9f9")),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
            ('TOPPADDING', (0, 0), (-1, -1), 3.5),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(txn_table)
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            f"<i>Displaying top {len(evidence_sorted)} of {len(evidence)} transactions by monetary value. "
            f"All transaction reference numbers are verifiable via bank core banking systems (CBS).</i>",
            small_style
        ))

    # ============================================================
    # PAGE 3: LEGAL MATRIX & ACTION FLOWCHART
    # ============================================================
    story.append(PageBreak())
    story.append(Paragraph("5. APPLICABLE LEGAL PROVISIONS", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 4))

    legal_sections = _get_legal_sections(pattern_type)
    legal_data = [[
        Paragraph("Legal Section", cell_header_style),
        Paragraph("Offence Classification", cell_header_style),
        Paragraph("Investigative Applicability", cell_header_style)
    ]]
    for s in legal_sections:
        legal_data.append([
            Paragraph(s['section'], cell_bold_style),
            Paragraph(s['title'], cell_bold_style),
            Paragraph(s['applicability'], cell_text_style)
        ])

    legal_table = Table(legal_data, colWidths=[105, 115, 260])
    legal_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1b3a6b")),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#f8f9f9")),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
        ('TOPPADDING', (0, 0), (-1, -1), 3.5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(legal_table)
    story.append(Spacer(1, 14))

    # Section 6: Recommended Actions - Flowchart
    story.append(Paragraph("6. RECOMMENDED INVESTIGATIVE ACTIONS (SOP FLOWCHART)", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "<b>Investigative Decision Flow:</b> Three-stage operational lifecycle structured to minimize response "
        "latency, freeze proceeds of crime before ATM withdrawal, and compile court-admissible evidence:",
        body_style
    ))
    story.append(Spacer(1, 4))

    # Generate and attach the flowchart image
    flowchart_img_path = os.path.join(os.path.dirname(output_filepath), "tmp_action_flowchart.png")
    generate_action_flowchart_image(flowchart_img_path)
    
    # 480 pt width x 224 pt height matches the 10.5x4.9 aspect ratio perfectly
    story.append(Image(flowchart_img_path, width=480, height=224))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "<i>Figure 1: Standard Operating Procedure (SOP) Flowchart for Cyber Financial Crimes. Color coding represents "
        "operational priority: Red = Emergency Containment (0-24h), Amber = Trail Expansion (24-72h), Blue = Judicial Prosecution (72h+).</i>",
        small_style
    ))

    # ============================================================
    # PAGE 4: DETAILED ACTION PROTOCOL & SIGN-OFF
    # ============================================================
    story.append(PageBreak())
    story.append(Paragraph("6.1 ACTIONABLE STEP-BY-STEP DIRECTIVES", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 6))

    actions = _get_recommended_actions(profile, pattern_type)
    for i, act in enumerate(actions, 1):
        priority_color = {
            'IMMEDIATE': '#C62828',
            'HIGH': '#EF6C00',
            'STANDARD': '#1565C0'
        }.get(act['priority'], '#555555')

        story.append(Paragraph(
            f"<b>{i}. [{act['priority']}] {act['action']}</b>",
            ParagraphStyle('ActionHead', parent=body_style,
                          textColor=colors.HexColor(priority_color),
                          fontSize=9.5, spaceAfter=2)
        ))
        story.append(Paragraph(act['detail'], body_style))
        story.append(Spacer(1, 3))

    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1b3a6b")))
    story.append(Spacer(1, 6))

    disclaimer = (
        "<b>DISCLAIMER & LEGAL ADMISSIBILITY CERTIFICATION NOTICE:</b> This case brief is auto-generated by the "
        "UPI Fraud Trail Reconstruction Engine based on forensic graph topology and behavioral heuristics. "
        "It serves as an investigative aid for the Investigating Officer (IO). "
        "Under Section 63(4) of the Bharatiya Sakshya Adhiniyam, 2023 (BSA), all electronic transaction records "
        "must be accompanied by formal certificates signed by designated Nodal Officers of the respective "
        "financial institutions prior to marking as exhibits in judicial proceedings."
    )
    story.append(Paragraph(disclaimer, small_style))
    story.append(Spacer(1, 20))

    # Signature blocks using Paragraphs for clean formatting
    sig_label_style = ParagraphStyle(
        'SigLabel', parent=styles['Normal'],
        fontSize=8.5, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=colors.HexColor("#1b3a6b")
    )
    sig_sub_style = ParagraphStyle(
        'SigSub', parent=styles['Normal'],
        fontSize=8, alignment=TA_CENTER, textColor=colors.HexColor("#555555")
    )

    sig_data = [
        ["", ""],
        ["_________________________________________", "_________________________________________"],
        [Paragraph("Investigating Officer (IO)", sig_label_style), Paragraph("Supervisory / Reviewing Officer", sig_label_style)],
        [Paragraph("Cyber Crime Police Station", sig_sub_style), Paragraph("Cyber Crime Police Station", sig_sub_style)],
        ["Name: _______________________________", "Name: _______________________________"],
        ["Rank / Belt No: ____________________", "Rank / Belt No: ____________________"],
        ["Date & Seal: ________________________", "Date & Seal: ________________________"],
    ]
    sig_table = Table(sig_data, colWidths=[240, 240])
    sig_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(sig_table)

    doc.build(story)

    # Clean up temp image
    if os.path.exists(flowchart_img_path):
        try:
            os.remove(flowchart_img_path)
        except Exception:
            pass

    return output_filepath

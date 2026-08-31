import pandas as pd
import networkx as nx
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import os


def extract_evidence_data(G, alert_row):
    """
    Extracts EXACTLY the transactions that triggered the alert -- no more,
    no less. Verified against real data: querying G.get_edge_data(u, v)
    naively (without a specific UTR) returns ALL parallel transactions
    between two accounts, which is often several unrelated ones -- this
    would silently over-cite background noise as fraud evidence. Fixed by
    parsing the exact (sender, utr, receiver) triples out of evidence_path
    and indexing the graph directly with the UTR as the edge key.
    """
    evidence_items = []
    target_account = alert_row['account_id']
    path_str = alert_row.get('evidence_path')

    edges_to_query = []  # (u, v, utr_key) triples

    if pd.notna(path_str) and path_str:
        # LAYERING: parse "Sender|UTR|Receiver,Sender|UTR|Receiver"
        edge_strings = str(path_str).split(',')
        for edge_str in edge_strings:
            parts = edge_str.split('|')
            if len(parts) == 3:
                u, utr_key, v = parts
                edges_to_query.append((u, v, utr_key))
    else:
        # FAN-IN: the whole aggregate pattern IS the evidence -- every
        # in-edge and out-edge for this account is legitimately relevant.
        for u, v, utr_key in G.in_edges(target_account, keys=True):
            edges_to_query.append((u, v, utr_key))
        for u, v, utr_key in G.out_edges(target_account, keys=True):
            edges_to_query.append((u, v, utr_key))

    edges_to_query = list(set(edges_to_query))

    for u, v, utr_key in edges_to_query:
        if G.has_edge(u, v, key=utr_key):
            data = G.edges[u, v, utr_key]
            evidence_items.append({
                'sender': u,
                'receiver': v,
                'utr': utr_key,
                'amount': data['amount'],
                'timestamp': data['timestamp'],
                'source': data.get('source_file', 'N/A'),
            })

    evidence_items.sort(key=lambda x: pd.to_datetime(x['timestamp']))
    return evidence_items


def generate_form_a_pdf(alert_row, G, output_filepath):
    """Generates a Delhi HC Form 'A' styled PDF for one specific alert."""
    doc = SimpleDocTemplate(output_filepath, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], alignment=1)
    story.append(Paragraph("CYBER CRIME INVESTIGATION REPORT", title_style))
    story.append(Spacer(1, 12))

    story.append(Paragraph("<b>Form 'A': Index of Electronic Exhibits</b>", styles['Heading2']))
    story.append(Paragraph("<i>Compliant with Section 63 BSA / Section 94 BNSS Disclosures</i>", styles['Normal']))
    story.append(Spacer(1, 20))

    story.append(Paragraph(f"<b>Target Account ID:</b> {alert_row['account_id']}", styles['Normal']))
    story.append(Paragraph(f"<b>Typology Detected:</b> {alert_row['rule']}", styles['Normal']))
    story.append(Paragraph(f"<b>Forensic Summary:</b> {alert_row['explanation']}", styles['Normal']))
    story.append(Spacer(1, 20))

    evidence_items = extract_evidence_data(G, alert_row)

    table_data = [["Exhibit No.", "Description of Electronic Record", "Proved By (Source)"]]
    for idx, item in enumerate(evidence_items, 1):
        exhibit_no = f"Ex-{idx}"
        description = (f"Transaction: Rs{item['amount']} on {item['timestamp']}\n"
                       f"Route: {item['sender']} -> {item['receiver']}\n"
                       f"UTR: {item['utr']}")
        proved_by = f"Sec 94 BNSS Return\n{item['source']}"
        table_data.append([exhibit_no, description, proved_by])

    t = Table(table_data, colWidths=[70, 260, 160])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#F8F9F9")),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(t)

    story.append(Spacer(1, 30))
    disclaimer = ("Note: The aforementioned records are derived from normalized bank/UPI statements. "
                  "Certification under Section 63(4) of the Bharatiya Sakshya Adhiniyam is required from "
                  "the respective Nodal Officers of the reporting entities for court admissibility.")
    story.append(Paragraph(f"<i>{disclaimer}</i>", styles['Italic']))

    doc.build(story)
    return output_filepath

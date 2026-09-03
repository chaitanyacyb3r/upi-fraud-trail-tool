"""Cross-reference Louvain communities against ACTUAL fraud rings.

Approach (A): Genuine ground-truth validation.
Uses enriched ground_truth_transactions.csv (with sender/receiver
account IDs + ring IDs) to build account->ring mapping.

IMPORTANT: Single-mule rings (n=1) are reported separately because
a single account is tautologically "all in one community" — it can't
fail the test. Only multi-mule rings (n>=2) constitute meaningful
validation of community detection.
"""
import pandas as pd
from collections import Counter

gt_txns = pd.read_csv("../data/ground_truth_transactions.csv")
comm_accts = pd.read_csv("../data/detected_communities_accounts.csv")
gt = pd.read_csv("../data/ground_truth.csv")

mules = set(gt[gt['role'] == 'mule']['account_id'])
acc_comm = dict(zip(comm_accts['account_id'], comm_accts['community_id']))

# Step 1: Build account -> ring mapping from ground truth
fraud = gt_txns[gt_txns['category'] == 'fraud'].copy()
fraud['ring'] = fraud['fraud_note'].str.extract(r'(ring\d+)')

account_rings = {}
for _, row in fraud.iterrows():
    ring = row['ring']
    sender = row['sender_account_id']
    receiver = row['receiver_account_id']
    if sender in mules:
        account_rings.setdefault(sender, set()).add(ring)
    if receiver in mules:
        account_rings.setdefault(receiver, set()).add(ring)

# Step 2: Build ring -> mule accounts mapping
ring_mules = {}
for acc, rings in account_rings.items():
    for r in rings:
        ring_mules.setdefault(r, set()).add(acc)

# Step 3: Split by ring size
multi_mule_rings = {r: accs for r, accs in ring_mules.items() if len(accs) >= 2}
single_mule_rings = {r: accs for r, accs in ring_mules.items() if len(accs) == 1}

print("GENUINE GROUND-TRUTH CROSS-REFERENCE (Split by Ring Size)")
print("=" * 70)
print(f"Total rings: {len(ring_mules)}")
print(f"  Multi-mule rings (n>=2, meaningful test): {len(multi_mule_rings)}")
print(f"  Single-mule rings (n=1, tautological): {len(single_mule_rings)}")

# ---- MULTI-MULE RINGS (the real test) ----
print()
print("=" * 70)
print("MULTI-MULE RINGS (Meaningful Validation)")
print("=" * 70)

multi_perfect = 0
for ring in sorted(multi_mule_rings.keys(), key=lambda x: int(x.replace('ring', ''))):
    ring_members = multi_mule_rings[ring]
    ring_num = int(ring.replace('ring', ''))
    ring_type = "layering" if ring_num <= 7 else "fan-in"

    comms_for_ring = {acc: acc_comm.get(acc, '?') for acc in sorted(ring_members)}
    unique_comms = set(comms_for_ring.values())
    all_in_one = len(unique_comms) == 1

    if all_in_one:
        multi_perfect += 1
        status = "ALL IN COMMUNITY " + str(list(unique_comms)[0])
    else:
        status = f"SPLIT across {unique_comms}"

    print(f"  {ring} ({ring_type}, {len(ring_members)} mules): {status}")
    for acc, c in sorted(comms_for_ring.items()):
        print(f"      {acc} -> community {c}")

print()
print(f"RESULT: {multi_perfect}/{len(multi_mule_rings)} multi-mule rings "
      f"perfectly isolated ({multi_perfect/len(multi_mule_rings)*100:.0f}%)")

# ---- SINGLE-MULE RINGS (tautological, report differently) ----
print()
print("=" * 70)
print("SINGLE-MULE FAN-IN RINGS (Tautological — reported as concentration)")
print("=" * 70)

single_comms = []
for ring in sorted(single_mule_rings.keys(), key=lambda x: int(x.replace('ring', ''))):
    acc = list(single_mule_rings[ring])[0]
    c = acc_comm.get(acc, '?')
    single_comms.append(c)

comm_counts = Counter(single_comms)
print(f"  {len(single_mule_rings)} single-mule fan-in accounts cluster into "
      f"only {len(comm_counts)} communities:")
for comm, count in comm_counts.most_common():
    print(f"    Community {comm}: {count} fan-in mules")

print()
print("  This shows victim-pool overlap concentration — fan-in mules")
print("  sharing overlapping victim sources get grouped together.")
print("  This is a real structural finding, but NOT a ring-match test")
print("  (n=1 rings can't fail the 'all in one community' check).")

# ---- FINAL SUMMARY ----
print()
print("=" * 70)
print("PRESENTATION-READY SUMMARY")
print("=" * 70)
print()
print(f"Pitch line: '{multi_perfect}/{len(multi_mule_rings)} multi-account "
      f"layering rings perfectly isolated by unsupervised Louvain")
print(f"  clustering — zero labels used.'")
print()
print(f"Supplementary: '{len(single_mule_rings)} single-mule fan-in accounts")
print(f"  cluster into {len(comm_counts)} communities by shared victim pools.'")

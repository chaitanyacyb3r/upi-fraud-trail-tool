"""Cross-reference Louvain communities against ACTUAL fraud rings.

Approach (A): Genuine ground-truth validation.
Uses the enriched ground_truth_transactions.csv (with sender/receiver
account IDs + fraud_note containing ring IDs) to build a proper
account->ring mapping, then checks whether Louvain communities align.

This is NOT the circular structural-consistency check (approach B) that
was correctly flagged as invalid. This uses independent ground truth.
"""
import pandas as pd

gt_txns = pd.read_csv("../data/ground_truth_transactions.csv")
comm_accts = pd.read_csv("../data/detected_communities_accounts.csv")
gt = pd.read_csv("../data/ground_truth.csv")

mules = set(gt[gt['role'] == 'mule']['account_id'])
acc_comm = dict(zip(comm_accts['account_id'], comm_accts['community_id']))

# Step 1: Build account -> ring mapping from ground truth
fraud = gt_txns[gt_txns['category'] == 'fraud'].copy()
fraud['ring'] = fraud['fraud_note'].str.extract(r'(ring\d+)')

account_rings = {}  # account_id -> set of ring IDs
for _, row in fraud.iterrows():
    ring = row['ring']
    sender = row['sender_account_id']
    receiver = row['receiver_account_id']
    if sender in mules:
        account_rings.setdefault(sender, set()).add(ring)
    if receiver in mules:
        account_rings.setdefault(receiver, set()).add(ring)

print("GENUINE GROUND-TRUTH CROSS-REFERENCE")
print("=" * 70)
print()

# Step 2: Build ring -> mule accounts mapping
ring_mules = {}
for acc, rings in account_rings.items():
    for r in rings:
        ring_mules.setdefault(r, set()).add(acc)

print(f"Total fraud rings: {len(ring_mules)}")
print(f"Total mules with ring assignments: {len(account_rings)}")
print()

# Step 3: For each ring, check if ALL its mules land in the same community
print("PER-RING ANALYSIS:")
print("-" * 70)

perfect = 0
split = 0
total = 0

for ring in sorted(ring_mules.keys(), key=lambda x: int(x.replace('ring', ''))):
    ring_members = ring_mules[ring]
    ring_num = int(ring.replace('ring', ''))
    ring_type = "layering" if ring_num <= 7 else "fan-in"

    comms_for_ring = {}
    for acc in sorted(ring_members):
        c = acc_comm.get(acc, '?')
        comms_for_ring[acc] = c

    unique_comms = set(comms_for_ring.values())
    all_in_one = len(unique_comms) == 1
    total += 1

    if all_in_one:
        perfect += 1
        status = "ALL IN COMMUNITY " + str(list(unique_comms)[0])
    else:
        split += 1
        status = f"SPLIT across {unique_comms}"

    print(f"  {ring} ({ring_type}, {len(ring_members)} mules): {status}")
    for acc, c in sorted(comms_for_ring.items()):
        print(f"      {acc} -> community {c}")

print()
print("=" * 70)
print("SUMMARY (Ground-Truth Validated)")
print("=" * 70)
print(f"Total rings: {total}")
print(f"Rings with ALL mules in same community: {perfect}/{total}")
print(f"Rings split across communities: {split}/{total}")

if total > 0:
    match_rate = perfect / total * 100
    print(f"Match rate: {match_rate:.0f}%")
    print()
    if match_rate > 70:
        print("VERDICT: Louvain communities correspond to actual fraud rings.")
        print("  This is GENUINE ground-truth validation (approach A),")
        print("  not structural self-consistency (approach B).")
    else:
        print("VERDICT: Partial correspondence only.")
else:
    print("ERROR: No rings found in ground truth data.")

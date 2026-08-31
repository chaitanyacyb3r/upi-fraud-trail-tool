"""
Phase 1 patch: exports account_id -> account_holder_name mapping,
needed by Phase 2's entity resolution step.

Run this from src/ alongside generate_dataset.py.
"""
import csv
from accounts import generate_accounts

def export_account_mapping(accounts, out_path):
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["account_id", "account_name"])
        for a in accounts:
            writer.writerow([a["account_id"], a["account_holder_name"]])

    # DUPLICATE NAME AUDIT -- this is the exact risk Gemini flagged:
    # dict(zip()) silently overwrites if two accounts share a name.
    names = [a["account_holder_name"] for a in accounts]
    seen = set()
    dupes = set()
    for n in names:
        if n in seen:
            dupes.add(n)
        seen.add(n)
    print(f"Exported {len(accounts)} accounts to {out_path}")
    if dupes:
        print(f"WARNING: {len(dupes)} duplicate name(s) found -- these will break "
              f"name-based entity resolution silently: {sorted(dupes)}")
    else:
        print("No duplicate names found in this generation run.")

if __name__ == "__main__":
    accs = generate_accounts()
    export_account_mapping(accs, "../data/account_mapping.csv")

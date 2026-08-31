import pandas as pd
import glob
import os

def parse_statements(statement_dir, mapping_csv_path, output_path):
    print("Starting Phase 2: Ingestion & Normalization (v3, quarantine logic)...")

    mapping_df = pd.read_csv(mapping_csv_path)

    duplicate_names_mask = mapping_df.duplicated(subset=['account_name'], keep=False)
    duplicate_names = set(mapping_df[duplicate_names_mask]['account_name'])

    safe_mapping_df = mapping_df[~duplicate_names_mask]
    safe_name_to_id = dict(zip(safe_mapping_df['account_name'], safe_mapping_df['account_id']))

    print("\n--- AUDIT 3: ENTITY RESOLUTION SAFETY CHECK ---")
    if duplicate_names:
        print(f"WARNING: Found {len(duplicate_names)} ambiguous names: {duplicate_names}")
    else:
        print("SUCCESS: All names unique.")

    all_files = glob.glob(os.path.join(statement_dir, "*.csv"))
    raw_dfs = []
    for file in all_files:
        df = pd.read_csv(file)
        filename = os.path.basename(file)
        owner_id = filename.split('_')[0]
        df['statement_owner_id'] = owner_id
        df['source_file'] = filename
        raw_dfs.append(df)
    raw_df = pd.concat(raw_dfs, ignore_index=True)
    initial_row_count = len(raw_df)

    credits_df = raw_df[raw_df['Transaction Type'] == 'Credit'].copy()
    debits_df = raw_df[raw_df['Transaction Type'] == 'Debit'].copy()

    def resolve_entity(name_series):
        return name_series.map(safe_name_to_id).fillna(
            name_series.apply(lambda x: f"AMBIGUOUS: {x}" if x in duplicate_names else f"UNKNOWN: {x}")
        )

    extracted_sender_names = credits_df['Transaction Details'].str.extract(r"Received from\s+(.+)")[0].str.strip()
    credits_df['sender_id'] = resolve_entity(extracted_sender_names)
    credits_df['receiver_id'] = credits_df['statement_owner_id']

    extracted_receiver_names = debits_df['Transaction Details'].str.extract(r"Paid to\s+(.+)")[0].str.strip()
    debits_df['receiver_id'] = resolve_entity(extracted_receiver_names)
    debits_df['sender_id'] = debits_df['statement_owner_id']

    normalized_df = pd.concat([credits_df, debits_df], ignore_index=True)

    final_df = pd.DataFrame({
        'sender': normalized_df['sender_id'],
        'receiver': normalized_df['receiver_id'],
        'amount': normalized_df['Amount'],
        'timestamp': normalized_df['Date'] + " " + normalized_df['Time'],
        'mode': normalized_df['Credit/Debit Instrument'],
        'reference_id': normalized_df['UTR'],
        'source': normalized_df['source_file'],
        'raw_narration': normalized_df['Transaction Details']
    })

    final_df = final_df.drop_duplicates(subset=['reference_id'], keep='first')

    print("\n--- INGESTION AUDIT REPORT ---")
    print(f"Audit 1: raw={initial_row_count}, final={len(final_df)}")

    missing_narration = final_df['raw_narration'].isna().sum()
    ambiguous_entities = final_df['sender'].str.startswith('AMBIGUOUS', na=False) | final_df['receiver'].str.startswith('AMBIGUOUS', na=False)
    unknown_entities = final_df['sender'].str.startswith('UNKNOWN', na=False) | final_df['receiver'].str.startswith('UNKNOWN', na=False)

    print(f"Audit 2: missing_narration={missing_narration}, ambiguous={ambiguous_entities.sum()}, unknown={unknown_entities.sum()}")

    # our own extra check: what does the ACC00316/ACC00519 situation look like now?
    print("\n--- OUR EXTRA CHECK: does ACC00316 still vanish? ---")
    lipika_rows = final_df[(final_df['sender'].astype(str).str.contains('Lipika', na=False)) |
                            (final_df['receiver'].astype(str).str.contains('Lipika', na=False))]
    print(f"Rows now involving 'Lipika Madan' in ANY form (real ID or AMBIGUOUS tag): {len(lipika_rows)}")
    print(lipika_rows[['sender', 'receiver']].drop_duplicates().to_string())

    final_df.to_csv(output_path, index=False)
    return final_df

if __name__ == "__main__":
    df = parse_statements("../data/statements", "../data/account_mapping.csv", "../data/normalized_transactions_v3.csv")

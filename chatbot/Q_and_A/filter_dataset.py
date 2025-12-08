"""
Filter and balance dataset by hop count and variant types.

Usage:
    python chatbot/Q_and_A/filter_dataset.py
"""
import pandas as pd
import os
import random
from collections import Counter

# Paths
INPUT_DIR = "chatbot/Q_and_A/output"
SUPPLEMENT_DIR = "chatbot/Q_and_A/output_1hop_comprehensive"
OUTPUT_DIR = "chatbot/Q_and_A/output_filtered"

# Target counts
TARGET_1HOP = 750
TARGET_2HOP = 450
TARGET_3HOP = 300

# Special variant targets for 2-hop and 3-hop
TARGET_2HOP_PARAPHRASE = 100
TARGET_2HOP_UNANSWERABLE = 100
TARGET_3HOP_PARAPHRASE = 51
TARGET_3HOP_UNANSWERABLE = 51


def load_csv_pair(questions_path: str, answers_path: str):
    """Load questions and answers CSV files."""
    questions_df = pd.read_csv(questions_path)
    answers_df = pd.read_csv(answers_path)
    return questions_df, answers_df


def get_hop_count(row):
    """Extract hop count from dataframe row."""
    return row.get('hop_count', 1)


def get_variant_type(row):
    """Extract variant type from dataframe row."""
    return row.get('variant_type', 'Normal')


def filter_and_balance(questions_df, answers_df, supplement_q_df, supplement_a_df, q_type: str):
    """
    Filter dataset according to rules:
    1. Remove all 1-hop and 4-hop (including PARAPHRASE_HARD/UNANSWERABLE)
    2. Add 1-hop from supplement to reach TARGET_1HOP total
    3. For 2-hop: keep 100 PARAPHRASE_HARD + 100 UNANSWERABLE + Normal to reach TARGET_2HOP
    4. For 3-hop: keep 50 PARAPHRASE_HARD + 50 UNANSWERABLE + Normal to reach TARGET_3HOP
    """
    print(f"\n{'='*60}")
    print(f"Processing {q_type} questions")
    print(f"{'='*60}")
    
    # Step 1: Categorize existing questions
    kept_rows = []
    removed_1hop = 0
    removed_4hop = 0
    
    # For 2-hop and 3-hop, separate by variant type
    kept_2hop_paraphrase = []
    kept_2hop_unanswerable = []
    kept_2hop_normal = []
    kept_3hop_paraphrase = []
    kept_3hop_unanswerable = []
    kept_3hop_normal = []
    
    for idx, row in questions_df.iterrows():
        hop = get_hop_count(row)
        variant = get_variant_type(row)
        
        if hop == 1:
            # Remove all 1-hop (including special)
            removed_1hop += 1
        elif hop == 4:
            removed_4hop += 1
        elif hop == 2:
            if variant == 'PARAPHRASE_HARD':
                kept_2hop_paraphrase.append(idx)
            elif variant == 'UNANSWERABLE':
                kept_2hop_unanswerable.append(idx)
            else:
                kept_2hop_normal.append(idx)
        elif hop == 3:
            if variant == 'PARAPHRASE_HARD':
                kept_3hop_paraphrase.append(idx)
            elif variant == 'UNANSWERABLE':
                kept_3hop_unanswerable.append(idx)
            else:
                kept_3hop_normal.append(idx)
        else:
            # Keep other hops as is
            kept_rows.append(idx)
    
    print(f"Original 1-hop removed (all): {removed_1hop}")
    print(f"Original 4-hop removed: {removed_4hop}")
    print(f"Original 2-hop: {len(kept_2hop_paraphrase)} PARAPHRASE + {len(kept_2hop_unanswerable)} UNANSWERABLE + {len(kept_2hop_normal)} Normal")
    print(f"Original 3-hop: {len(kept_3hop_paraphrase)} PARAPHRASE + {len(kept_3hop_unanswerable)} UNANSWERABLE + {len(kept_3hop_normal)} Normal")
    
    # Step 2: Sample 2-hop and 3-hop
    random.seed(42)
    
    # For 2-hop: sample each variant type to target
    if len(kept_2hop_paraphrase) > TARGET_2HOP_PARAPHRASE:
        kept_2hop_paraphrase = random.sample(kept_2hop_paraphrase, TARGET_2HOP_PARAPHRASE)
    if len(kept_2hop_unanswerable) > TARGET_2HOP_UNANSWERABLE:
        kept_2hop_unanswerable = random.sample(kept_2hop_unanswerable, TARGET_2HOP_UNANSWERABLE)
    
    # Calculate how many normal needed for 2-hop
    current_2hop_special = len(kept_2hop_paraphrase) + len(kept_2hop_unanswerable)
    needed_2hop_normal = max(0, TARGET_2HOP - current_2hop_special)
    if len(kept_2hop_normal) > needed_2hop_normal:
        kept_2hop_normal = random.sample(kept_2hop_normal, needed_2hop_normal)
    
    kept_2hop = kept_2hop_paraphrase + kept_2hop_unanswerable + kept_2hop_normal
    print(f"Final 2-hop: {len(kept_2hop_paraphrase)} PARAPHRASE + {len(kept_2hop_unanswerable)} UNANSWERABLE + {len(kept_2hop_normal)} Normal = {len(kept_2hop)} total")
    
    # For 3-hop: sample each variant type to target
    if len(kept_3hop_paraphrase) > TARGET_3HOP_PARAPHRASE:
        kept_3hop_paraphrase = random.sample(kept_3hop_paraphrase, TARGET_3HOP_PARAPHRASE)
    if len(kept_3hop_unanswerable) > TARGET_3HOP_UNANSWERABLE:
        kept_3hop_unanswerable = random.sample(kept_3hop_unanswerable, TARGET_3HOP_UNANSWERABLE)
    
    # Calculate how many normal needed for 3-hop
    current_3hop_special = len(kept_3hop_paraphrase) + len(kept_3hop_unanswerable)
    needed_3hop_normal = max(0, TARGET_3HOP - current_3hop_special)
    if len(kept_3hop_normal) > needed_3hop_normal:
        kept_3hop_normal = random.sample(kept_3hop_normal, needed_3hop_normal)
    
    kept_3hop = kept_3hop_paraphrase + kept_3hop_unanswerable + kept_3hop_normal
    print(f"Final 3-hop: {len(kept_3hop_paraphrase)} PARAPHRASE + {len(kept_3hop_unanswerable)} UNANSWERABLE + {len(kept_3hop_normal)} Normal = {len(kept_3hop)} total")
    
    # Step 3: Calculate how many 1-hop to add from supplement
    needed_1hop = TARGET_1HOP  # All 1-hop from supplement since we removed all original
    print(f"\nNeed to add {needed_1hop} 1-hop questions from supplement")
    
    # Get 1-hop from supplement
    supplement_1hop_indices = []
    for idx, row in supplement_q_df.iterrows():
        if get_hop_count(row) == 1:
            supplement_1hop_indices.append(idx)
    
    print(f"Available 1-hop in supplement: {len(supplement_1hop_indices)}")
    
    if needed_1hop > 0 and len(supplement_1hop_indices) > 0:
        if len(supplement_1hop_indices) >= needed_1hop:
            selected_supplement = random.sample(supplement_1hop_indices, needed_1hop)
        else:
            selected_supplement = supplement_1hop_indices
            print(f"Warning: Not enough supplement questions, using all {len(selected_supplement)}")
    else:
        selected_supplement = []
    
    # Step 4: Build final dataframes
    # Combine indices from original (no 1-hop from original)
    final_original_indices = kept_2hop + kept_3hop + kept_rows
    
    # Get original questions/answers
    final_q_original = questions_df.loc[final_original_indices].copy()
    final_a_original = answers_df[answers_df['id'].isin(final_q_original['id'])].copy()
    
    # Get supplement questions/answers
    if selected_supplement:
        supplement_q_selected = supplement_q_df.loc[selected_supplement].copy()
        supplement_a_selected = supplement_a_df[supplement_a_df['id'].isin(supplement_q_selected['id'])].copy()
        
        # Renumber IDs to avoid conflicts
        max_id = final_q_original['id'].max() if len(final_q_original) > 0 else 0
        id_mapping = {old_id: max_id + i + 1 for i, old_id in enumerate(supplement_q_selected['id'])}
        
        supplement_q_selected['id'] = supplement_q_selected['id'].map(id_mapping)
        supplement_a_selected['id'] = supplement_a_selected['id'].map(id_mapping)
        
        # Combine
        final_q = pd.concat([final_q_original, supplement_q_selected], ignore_index=True)
        final_a = pd.concat([final_a_original, supplement_a_selected], ignore_index=True)
    else:
        final_q = final_q_original
        final_a = final_a_original
    
    # Re-sort by id
    final_q = final_q.sort_values('id').reset_index(drop=True)
    final_a = final_a.sort_values('id').reset_index(drop=True)
    
    # Renumber IDs sequentially
    new_ids = list(range(1, len(final_q) + 1))
    old_to_new = dict(zip(final_q['id'], new_ids))
    final_q['id'] = new_ids
    final_a['id'] = final_a['id'].map(old_to_new)
    
    return final_q, final_a, len(selected_supplement)


def generate_statistics(mcq_q, mcq_a, tf_q, tf_a, output_path: str):
    """Generate statistics report."""
    
    def count_by_hop_and_variant(df):
        stats = {}
        for hop in [1, 2, 3, 4]:
            hop_df = df[df['hop_count'] == hop]
            stats[hop] = {
                'total': len(hop_df),
                'Normal': len(hop_df[hop_df['variant_type'] == 'Normal']),
                'PARAPHRASE_HARD': len(hop_df[hop_df['variant_type'] == 'PARAPHRASE_HARD']),
                'UNANSWERABLE': len(hop_df[hop_df['variant_type'] == 'UNANSWERABLE']),
            }
        return stats
    
    mcq_stats = count_by_hop_and_variant(mcq_q)
    tf_stats = count_by_hop_and_variant(tf_q)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write("DATASET STATISTICS AFTER FILTERING\n")
        f.write("=" * 70 + "\n\n")
        
        f.write(f"Total MCQ questions: {len(mcq_q)}\n")
        f.write(f"Total TRUE_FALSE questions: {len(tf_q)}\n\n")
        
        f.write("-" * 70 + "\n")
        f.write("MCQ QUESTIONS BY HOP COUNT\n")
        f.write("-" * 70 + "\n")
        for hop in [1, 2, 3, 4]:
            s = mcq_stats[hop]
            if s['total'] > 0:
                f.write(f"\n{hop}-hop: {s['total']} total\n")
                f.write(f"  - Normal: {s['Normal']}\n")
                f.write(f"  - PARAPHRASE_HARD: {s['PARAPHRASE_HARD']}\n")
                f.write(f"  - UNANSWERABLE: {s['UNANSWERABLE']}\n")
        
        f.write("\n" + "-" * 70 + "\n")
        f.write("TRUE_FALSE QUESTIONS BY HOP COUNT\n")
        f.write("-" * 70 + "\n")
        for hop in [1, 2, 3, 4]:
            s = tf_stats[hop]
            if s['total'] > 0:
                f.write(f"\n{hop}-hop: {s['total']} total\n")
                f.write(f"  - Normal: {s['Normal']}\n")
                f.write(f"  - PARAPHRASE_HARD: {s['PARAPHRASE_HARD']}\n")
                f.write(f"  - UNANSWERABLE: {s['UNANSWERABLE']}\n")
        
        f.write("\n" + "=" * 70 + "\n")
        f.write("SUMMARY\n")
        f.write("=" * 70 + "\n")
        
        mcq_total_by_hop = {hop: mcq_stats[hop]['total'] for hop in [1, 2, 3, 4]}
        tf_total_by_hop = {hop: tf_stats[hop]['total'] for hop in [1, 2, 3, 4]}
        
        f.write(f"\nMCQ: 1-hop={mcq_total_by_hop[1]}, 2-hop={mcq_total_by_hop[2]}, 3-hop={mcq_total_by_hop[3]}, 4-hop={mcq_total_by_hop[4]}\n")
        f.write(f"TF:  1-hop={tf_total_by_hop[1]}, 2-hop={tf_total_by_hop[2]}, 3-hop={tf_total_by_hop[3]}, 4-hop={tf_total_by_hop[4]}\n")
    
    print(f"\nStatistics saved to: {output_path}")


def main():
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Load original data
    print("Loading original data...")
    mcq_q, mcq_a = load_csv_pair(
        os.path.join(INPUT_DIR, "mcq_questions.csv"),
        os.path.join(INPUT_DIR, "mcq_answers.csv")
    )
    tf_q, tf_a = load_csv_pair(
        os.path.join(INPUT_DIR, "true_false_questions.csv"),
        os.path.join(INPUT_DIR, "true_false_answers.csv")
    )
    
    print(f"Original MCQ: {len(mcq_q)} questions")
    print(f"Original TF: {len(tf_q)} questions")
    
    # Load supplement data (1-hop comprehensive)
    print("\nLoading supplement 1-hop data...")
    supp_mcq_q, supp_mcq_a = load_csv_pair(
        os.path.join(SUPPLEMENT_DIR, "mcq_questions.csv"),
        os.path.join(SUPPLEMENT_DIR, "mcq_answers.csv")
    )
    supp_tf_q, supp_tf_a = load_csv_pair(
        os.path.join(SUPPLEMENT_DIR, "true_false_questions.csv"),
        os.path.join(SUPPLEMENT_DIR, "true_false_answers.csv")
    )
    
    print(f"Supplement MCQ: {len(supp_mcq_q)} questions")
    print(f"Supplement TF: {len(supp_tf_q)} questions")
    
    # Filter MCQ
    final_mcq_q, final_mcq_a, mcq_added = filter_and_balance(
        mcq_q, mcq_a, supp_mcq_q, supp_mcq_a, "MCQ"
    )
    
    # Filter TF
    final_tf_q, final_tf_a, tf_added = filter_and_balance(
        tf_q, tf_a, supp_tf_q, supp_tf_a, "TRUE_FALSE"
    )
    
    # Save filtered data
    print("\n" + "=" * 60)
    print("Saving filtered data...")
    print("=" * 60)
    
    final_mcq_q.to_csv(os.path.join(OUTPUT_DIR, "mcq_questions.csv"), index=False)
    final_mcq_a.to_csv(os.path.join(OUTPUT_DIR, "mcq_answers.csv"), index=False)
    final_tf_q.to_csv(os.path.join(OUTPUT_DIR, "true_false_questions.csv"), index=False)
    final_tf_a.to_csv(os.path.join(OUTPUT_DIR, "true_false_answers.csv"), index=False)
    
    print(f"Saved MCQ: {len(final_mcq_q)} questions (added {mcq_added} from supplement)")
    print(f"Saved TF: {len(final_tf_q)} questions (added {tf_added} from supplement)")
    
    # Generate statistics
    generate_statistics(
        final_mcq_q, final_mcq_a, final_tf_q, final_tf_a,
        os.path.join(OUTPUT_DIR, "statistics.txt")
    )
    
    print("\nDone!")


if __name__ == '__main__':
    main()

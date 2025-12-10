
import argparse
import json
import logging
import os
import random
import sys
import pandas as pd
from dotenv import load_dotenv

# Add current directory to path to allow imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from kg_utils import KnowledgeGraph
from generate_dataset import DatasetGenerator
from llm_client import create_llm_client, format_variant_prompt, parse_llm_response
import time
from tqdm import tqdm

def supplement_true_false(kg_path, output_dir, count=10):
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    # Load KG
    logger.info(f"Loading KG from {kg_path}...")
    kg = KnowledgeGraph(kg_path)
    
    # Config
    config = {
        'seed': random.randint(1000, 9999), # Random seed to avoid duplicates
        'max_hop': 4,
        'llm_model': 'gemini-2.5-flash-lite' # Not used for normal generation but required by init
    }
    
    generator = DatasetGenerator(kg, config)
    
    # Generate candidates
    logger.info("Generating candidates...")
    # Use internal methods to get candidates
    single_hop_candidates = generator._generate_single_hop_candidates()
    multi_hop_candidates = generator._generate_multi_hop_candidates()
    
    logger.info(f"Generated {len(single_hop_candidates)} single-hop and {len(multi_hop_candidates)} multi-hop candidates.")
    
    # Generate questions
    logger.info(f"Generating {count} True/False questions...")
    
    # We want a mix. Let's say 80% multi, 20% single.
    multi_count = int(count * 0.8)
    single_count = count - multi_count
    
    # Ensure we have enough candidates
    if len(multi_hop_candidates) < multi_count:
        logger.warning(f"Not enough multi-hop candidates ({len(multi_hop_candidates)} < {multi_count}). Using all available.")
        multi_count = len(multi_hop_candidates)
        single_count = count - multi_count
        
    new_questions = generator.generate_questions_by_type(
        multi_hop_candidates, 
        single_hop_candidates, 
        multi_count, 
        single_count, 
        'TRUE_FALSE'
    )
    
    # LLM Paraphrasing
    logger.info("Paraphrasing questions with LLM...")
    try:
        llm_client = create_llm_client(model=config['llm_model'])
        
        for i, q in enumerate(tqdm(new_questions, desc="LLM Paraphrasing")):
            try:
                # Format prompt
                ans_val = q['answer'].get('answer', 'True') if isinstance(q['answer'], dict) else str(q['answer'])
                
                prompt = format_variant_prompt(
                    seed_question=q['question'],
                    q_type='TRUE_FALSE',
                    hop_count=q['hop_count'],
                    reasoning_path=q['reasoning_path'],
                    answer=ans_val
                )
                
                # Call LLM
                response = llm_client.generate(prompt, temperature=0.7, max_tokens=1500)
                parsed = parse_llm_response(response)
                
                selected_variant = None
                if parsed and 'variants' in parsed:
                    # Prefer PARAPHRASE_HARD
                    for v in parsed['variants']:
                        if v.get('variant_type') == 'PARAPHRASE_HARD':
                            selected_variant = v
                            break
                    
                    # If not found, check if we have any variant
                    if not selected_variant and len(parsed['variants']) > 0:
                        # If we only have UNANSWERABLE, we should be careful.
                        # UNANSWERABLE changes the ground truth to "Not Given".
                        # For now, let's only accept PARAPHRASE_HARD to keep the answer valid.
                        logger.warning(f"Only found {parsed['variants'][0]['variant_type']}, skipping to keep answer valid.")
                        selected_variant = None

                if selected_variant:
                    q['question'] = selected_variant['question']
                    q['variant_type'] = selected_variant['variant_type']
                    logger.info(f"Paraphrased: {q['variant_type']}")
                else:
                    q['variant_type'] = 'Normal'
                    logger.warning("No suitable PARAPHRASE_HARD variant returned")
                    
                time.sleep(2) # Sleep to avoid rate limit
                
            except Exception as e:
                logger.error(f"LLM failed for q {i}: {e}")
                q['variant_type'] = 'Normal'
                
    except Exception as e:
        logger.error(f"Failed to init LLM: {e}")
        # Continue with Normal questions
    
    # Load existing files
    questions_file = os.path.join(output_dir, 'true_false_questions.csv')
    answers_file = os.path.join(output_dir, 'true_false_answers.csv')
    
    if os.path.exists(questions_file) and os.path.exists(answers_file):
        df_q = pd.read_csv(questions_file)
        df_a = pd.read_csv(answers_file)
        
        last_id = df_q['id'].max()
        logger.info(f"Current last ID: {last_id}")
    else:
        logger.info("Existing files not found. Creating new.")
        df_q = pd.DataFrame(columns=['id', 'question', 'hop_count', 'reasoning_path', 'variant_type'])
        df_a = pd.DataFrame(columns=['id', 'answer'])
        last_id = 0
        
    # Append new questions
    q_rows = []
    a_rows = []
    
    for i, q in enumerate(new_questions):
        new_id = last_id + i + 1
        
        q_rows.append({
            'id': new_id,
            'question': q['question'],
            'hop_count': q['hop_count'],
            'reasoning_path': q['reasoning_path'],
            'variant_type': q.get('variant_type', 'Normal')
        })
        
        # Handle answer format (might be dict or string)
        ans = q['answer']
        if isinstance(ans, dict):
            ans_val = ans.get('answer', True)
        else:
            ans_val = ans
            
        # Map to Vietnamese
        if str(ans_val).lower() == 'true':
            ans_str = "Đúng"
        else:
            ans_str = "Sai"
            
        a_rows.append({
            'id': new_id,
            'answer': ans_str
        })
        
    new_df_q = pd.DataFrame(q_rows)
    new_df_a = pd.DataFrame(a_rows)
    
    # Concat
    final_df_q = pd.concat([df_q, new_df_q], ignore_index=True)
    final_df_a = pd.concat([df_a, new_df_a], ignore_index=True)
    
    # Save
    final_df_q.to_csv(questions_file, index=False, encoding='utf-8')
    final_df_a.to_csv(answers_file, index=False, encoding='utf-8')
    
    logger.info(f"Added {len(new_questions)} questions. New total: {len(final_df_q)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--kg", default="data/processed/graph/knowledge_graph_enriched.json")
    parser.add_argument("--out_dir", default="chatbot/Q_and_A/output")
    parser.add_argument("--count", type=int, default=10)
    args = parser.parse_args()
    
    supplement_true_false(args.kg, args.out_dir, args.count)

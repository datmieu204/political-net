"""
Test accuracy of Gemini model on generated questions.
Compare Gemini's answers with ground truth answers.
"""

import os
import sys
import json
import pandas as pd
import google.generativeai as genai
from tqdm import tqdm
import time
from collections import defaultdict, Counter
import logging
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from utils.api_key_rotator import APIKeyRotator

# Setup logging
def setup_logging(output_dir):
    """Setup logging to file and console."""
    os.makedirs(output_dir, exist_ok=True)
    
    log_file = os.path.join(output_dir, 'test_accuracy.log')
    
    # Create logger
    logger = logging.getLogger('test_accuracy')
    logger.setLevel(logging.DEBUG)
    
    # File handler
    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    
    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    
    # Add handlers
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    logger.info(f"Logging to {log_file}")
    return logger


def load_questions_and_answers(question_file, answer_file):
    """Load questions and answers from CSV files."""
    questions_df = pd.read_csv(question_file, encoding='utf-8')
    answers_df = pd.read_csv(answer_file, encoding='utf-8')
    
    # Merge on id
    merged = pd.merge(questions_df, answers_df, on='id')
    return merged


def ask_gemini(question, model, logger, key_rotator, q_type, max_retries=None):
    """Ask Gemini a question and get the answer. Will retry indefinitely until success."""
    logger.debug(f"Asking Gemini: {question[:100]}...")
    
    # Add instruction for concise answer based on question type
    if q_type == 'MCQ':
        prompt = f"""Câu hỏi: {question}

QUAN TRỌNG: Chỉ trả lời ĐÚNG MỘT CHỮ CÁI duy nhất (A, B, C, hoặc D). KHÔNG giải thích, KHÔNG phân tích, KHÔNG thêm bất kỳ văn bản nào khác. Chỉ viết một chữ cái."""
    else:  # TRUE_FALSE
        prompt = f"""Câu hỏi: {question}

QUAN TRỌNG: Chỉ trả lời ĐÚNG MỘT TỪ duy nhất (Đúng, Sai, hoặc Không có dữ kiện). KHÔNG giải thích, KHÔNG phân tích, KHÔNG thêm bất kỳ văn bản nào khác. Chỉ viết một từ."""
    
    # Track attempts
    attempt = 0
    
    # Retry indefinitely until we get a response
    while True:
        try:
            # Log which key we're using
            if attempt == 1 or attempt % 10 == 0:
                logger.info(f"Using key: {key_rotator.get_current_key_name()}, attempt: {attempt}")
            
            response = model.generate_content(prompt)
            
            # Log raw response
            logger.debug(f"Raw response received: {response}")
            
            # Check if response has candidates
            if not response.candidates:
                logger.warning(f"No candidates in response. Prompt feedback: {response.prompt_feedback}")
                return None
            
            # Check finish reason
            candidate = response.candidates[0]
            logger.debug(f"Finish reason: {candidate.finish_reason}")
            
            if candidate.finish_reason not in [1, 'STOP']:  # 1 = STOP
                logger.warning(f"Unexpected finish reason: {candidate.finish_reason}")
            
            if response.text:
                logger.debug(f"Response text: {response.text[:200]}...")
                return response.text.strip()
            else:
                logger.warning("Empty response text")
                return None
                
        except Exception as e:
            logger.warning(f"Error on attempt {attempt}: {str(e)[:200]}")
            
            # Use key_rotator's handle_api_error (same as Q_and_A code)
            if key_rotator.handle_api_error(e):
                logger.info(f"Rotated to key: {key_rotator.get_current_key_name()}")
                
                # Wait 5s after key rotation
                time.sleep(5)
                
                # Reinitialize model with new key (important!)
                model = genai.GenerativeModel('gemini-2.5-flash-lite')
                continue
            
            # If not a key rotation case, do exponential backoff
            wait_time = min(10, 2 ** min(attempt, 3))  # 1, 2, 4, 8, max 10s
            logger.info(f"Waiting {wait_time}s before retry...")
            time.sleep(wait_time)
            continue
    return None


def extract_answer_from_response(response, q_type):
    """Extract answer from Gemini's response."""
    if not response:
        return None
    
    response_lower = response.lower()
    
    if q_type == 'MCQ':
        # Check last 500 chars for final answer
        last_part = response_lower[-500:]
        
        # Look for conclusive statements with answer
        conclusive_phrases = ['đáp án chính xác là', 'đáp án đúng là', 'đáp án là', 
                              'kết luận', 'do đó', 'vì vậy', 'tóm lại']
        
        for phrase in conclusive_phrases:
            if phrase in last_part:
                # Find the option after the phrase
                idx = last_part.rfind(phrase)
                after_phrase = last_part[idx:idx+150]
                
                # Look for **A**, **B**, etc or just A), B), etc (both upper and lower case)
                for option in ['A', 'B', 'C', 'D']:
                    if f'**{option.lower()}**' in after_phrase or \
                       f'**{option}**' in after_phrase or \
                       f'**{option.lower()})**' in after_phrase or \
                       f'**{option})**' in after_phrase or \
                       f'{option.lower()})' in after_phrase or \
                       f'{option})' in after_phrase or \
                       f' {option.lower()} ' in after_phrase or \
                       f' {option} ' in after_phrase or \
                       f'chọn {option.lower()}' in after_phrase or \
                       f'lựa {option.lower()}' in after_phrase:
                        return option
        
        # Look for A, B, C, or D in general response
        for option in ['A', 'B', 'C', 'D']:
            if f'đáp án {option.lower()}' in response_lower or \
               f'đáp án: {option.lower()}' in response_lower or \
               f'câu {option.lower()}' in response_lower:
                return option
        
        # Try to find standalone letter at the beginning
        first_line = response.split('\n')[0].strip()
        if first_line in ['A', 'B', 'C', 'D', 'a', 'b', 'c', 'd']:
            return first_line.upper()
        
        # Check for "Không có dữ kiện" variations
        if 'không có dữ kiện' in response_lower or 'không có thông tin' in response_lower or \
           'not given' in response_lower or 'thiếu thông tin' in response_lower:
            return 'D'  # Usually unanswerable is option D
            
    else:  # TRUE_FALSE
        # Strategy: Find the ABSOLUTE LAST mention of Đúng/Sai in the response
        
        # First check the very beginning (first 100 chars) for immediate answer
        first_part = response_lower[:100]
        if 'câu trả lời là **sai**' in first_part:
            return 'Sai'
        if 'câu trả lời là **đúng**' in first_part:
            return 'Đúng'
        if first_part.startswith('**sai**') or first_part.startswith('sai.'):
            return 'Sai'
        if first_part.startswith('**đúng**') or first_part.startswith('đúng.'):
            return 'Đúng'
        
        # Find the LAST occurrence of conclusive Đúng or Sai
        import re
        
        # Search for patterns indicating final answer (prioritize patterns that appear later)
        conclusive_patterns = [
            r'toàn bộ câu.*?\*\*sai\*\*',
            r'toàn bộ câu.*?\*\*đúng\*\*',
            r'câu này là.*?\*\*sai\*\*',
            r'câu này là.*?\*\*đúng\*\*',
            r'do đó.*?\*\*sai\*\*',
            r'do đó.*?\*\*đúng\*\*',
            r'vì vậy.*?\*\*sai\*\*',
            r'vì vậy.*?\*\*đúng\*\*',
            r'câu trả lời là.*?\*\*sai\*\*',
            r'câu trả lời là.*?\*\*đúng\*\*',
            r'thông tin.*?là.*?\*\*sai\*\*',
            r'thông tin.*?là.*?\*\*đúng\*\*',
        ]
        
        last_position = -1
        last_answer = None
        
        for pattern in conclusive_patterns:
            matches = list(re.finditer(pattern, response_lower))
            if matches:
                # Get the last match
                match = matches[-1]
                if match.start() > last_position:
                    last_position = match.start()
                    # Determine if it's Đúng or Sai
                    if 'sai' in match.group():
                        last_answer = 'Sai'
                    else:
                        last_answer = 'Đúng'
        
        if last_answer:
            return last_answer
        
        # Check for uncertainty indicators (for UNANSWERABLE questions)
        uncertainty_phrases = ['có khả năng', 'có vai trò gián tiếp', 'không trực tiếp',
                              'không rõ ràng', 'cần thêm thông tin', 'không chắc chắn']
        has_uncertainty = any(phrase in response_lower for phrase in uncertainty_phrases)
        
        # Check for "Không có dữ kiện" 
        no_data_phrases = ['không có dữ kiện', 'không có thông tin', 
                          'thiếu thông tin', 'không đủ thông tin']
        has_no_data = any(phrase in response_lower for phrase in no_data_phrases)
        
        # If uncertain or no data, and no clear Đúng/Sai conclusion
        if (has_uncertainty or has_no_data) and last_answer is None:
            return 'Không có dữ kiện'
        
        # Look in last 300 chars for any Đúng/Sai in bold
        last_part = response_lower[-300:]
        
        # Find LAST occurrence of **đúng** or **sai**
        last_dung_pos = last_part.rfind('**đúng**')
        last_sai_pos = last_part.rfind('**sai**')
        
        if last_sai_pos > last_dung_pos:
            return 'Sai'
        elif last_dung_pos > last_sai_pos:
            return 'Đúng'
        
        # Final fallback: count occurrences
        dung_count = response_lower.count('đúng')
        sai_count = response_lower.count('sai')
        
        if sai_count > dung_count:
            return 'Sai'
        elif dung_count > sai_count:
            return 'Đúng'
    
    return None


def get_variant_type(row):
    """Get variant type from row."""
    if 'variant_type' in row and pd.notna(row['variant_type']):
        vtype = str(row['variant_type']).strip()
        if vtype in ['Normal', 'ORIGINAL']:
            return 'Normal'
        elif vtype == 'PARAPHRASE_HARD':
            return 'Paraphrase'
        elif vtype == 'UNANSWERABLE':
            return 'Unanswerable'
    return 'Normal'


def test_questions(data_dir, output_dir, q_type, sample_size=None):
    """
    Test questions with Gemini and compare with ground truth.
    
    Args:
        data_dir: Directory containing question and answer files
        output_dir: Directory to save results
        q_type: 'MCQ' or 'TRUE_FALSE'
        sample_size: Number of questions to test (None = all)
    """
    # Setup logging
    logger = setup_logging(output_dir)
    
    print(f"\n{'='*60}")
    print(f"Testing {q_type} Questions")
    print(f"{'='*60}")
    
    logger.info(f"Starting {q_type} test")
    
    # Load data
    if q_type == 'MCQ':
        q_file = os.path.join(data_dir, 'mcq_questions.csv')
        a_file = os.path.join(data_dir, 'mcq_answers.csv')
    else:
        q_file = os.path.join(data_dir, 'true_false_questions.csv')
        a_file = os.path.join(data_dir, 'true_false_answers.csv')
    
    print(f"Loading questions from {q_file}")
    logger.info(f"Loading questions from {q_file}")
    data = load_questions_and_answers(q_file, a_file)
    
    if sample_size and sample_size < len(data):
        data = data.sample(n=sample_size, random_state=42)
        print(f"Sampled {sample_size} questions")
    
    print(f"Total questions: {len(data)}")
    
    # Initialize Gemini
    print("Initializing Gemini model...")
    key_rotator = APIKeyRotator()  # This automatically configures the first key
    
    # Configure safety settings to be less restrictive
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]
    
    # Use same model as Q_and_A generation
    model = genai.GenerativeModel(
        'gemini-2.5-flash-lite',  # Same model used in generate_dataset_large.py
        safety_settings=safety_settings
    )
    
    logger.info(f"Using model: gemini-2.5-flash-lite")
    
    # Statistics
    stats = {
        'total': 0,
        'correct': 0,
        'incorrect': 0,
        'no_response': 0,
        'by_hop': defaultdict(lambda: {'total': 0, 'correct': 0}),
        'by_variant': defaultdict(lambda: {'total': 0, 'correct': 0})
    }
    
    results = []
    
    # Test each question
    print(f"\nTesting questions...")
    for idx, row in tqdm(data.iterrows(), total=len(data), desc="Processing"):
        question = row['question']
        ground_truth = row['answer']
        hop_count = row['hop_count']
        variant_type = get_variant_type(row)
        
        logger.info(f"Testing question {row['id']} (hop={hop_count}, type={variant_type})")
        
        # Ask Gemini
        response = ask_gemini(question, model, logger, key_rotator, q_type)
        
        # Clean response (strip whitespace)
        answer = response.strip() if response else None
        
        logger.debug(f"Gemini answer: {answer}, Ground truth: {ground_truth}")
        
        # Compare
        is_correct = (answer == ground_truth)
        
        # Update stats
        stats['total'] += 1
        if answer is None:
            stats['no_response'] += 1
        elif is_correct:
            stats['correct'] += 1
            stats['by_hop'][hop_count]['correct'] += 1
            stats['by_variant'][variant_type]['correct'] += 1
        else:
            stats['incorrect'] += 1
        
        stats['by_hop'][hop_count]['total'] += 1
        stats['by_variant'][variant_type]['total'] += 1
        
        # Store result
        result = {
            'id': row['id'],
            'question': question,
            'ground_truth': ground_truth,
            'gemini_response': answer,
            'is_correct': is_correct,
            'hop_count': hop_count,
            'variant_type': variant_type
        }
        results.append(result)
        
        # Save to file IMMEDIATELY after each question (real-time)
        os.makedirs(output_dir, exist_ok=True)
        results_file = os.path.join(output_dir, f'{q_type.lower()}_test_results.json')
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.debug(f"Saved result to {results_file} (total: {len(results)})")
        
        # Rate limiting - 1 second between requests
        time.sleep(1)
    
    # Save results
    os.makedirs(output_dir, exist_ok=True)
    
    results_file = os.path.join(output_dir, f'{q_type.lower()}_test_results.json')
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved detailed results to {results_file}")
    
    # Print statistics
    print(f"\n{'='*60}")
    print("OVERALL STATISTICS")
    print(f"{'='*60}")
    print(f"Total questions: {stats['total']}")
    print(f"Correct: {stats['correct']} ({stats['correct']/stats['total']*100:.2f}%)")
    print(f"Incorrect: {stats['incorrect']} ({stats['incorrect']/stats['total']*100:.2f}%)")
    print(f"No response: {stats['no_response']} ({stats['no_response']/stats['total']*100:.2f}%)")
    
    logger.info(f"OVERALL: {stats['correct']}/{stats['total']} correct ({stats['correct']/stats['total']*100:.2f}%)")
    logger.info(f"No response: {stats['no_response']}")
    
    print(f"\n{'='*60}")
    print("STATISTICS BY HOP COUNT")
    print(f"{'='*60}")
    for hop in sorted(stats['by_hop'].keys()):
        hop_stats = stats['by_hop'][hop]
        accuracy = hop_stats['correct'] / hop_stats['total'] * 100
        print(f"{hop}-hop: {hop_stats['correct']}/{hop_stats['total']} correct ({accuracy:.2f}%)")
    
    print(f"\n{'='*60}")
    print("STATISTICS BY VARIANT TYPE")
    print(f"{'='*60}")
    for variant in sorted(stats['by_variant'].keys()):
        variant_stats = stats['by_variant'][variant]
        accuracy = variant_stats['correct'] / variant_stats['total'] * 100
        print(f"{variant}: {variant_stats['correct']}/{variant_stats['total']} correct ({accuracy:.2f}%)")
    
    # Calculate metrics manually (without sklearn)
    # Filter out samples with no response
    valid_results = [r for r in results if r['gemini_response'] is not None]
    
    metrics = {}
    if valid_results:
        y_true = [r['ground_truth'] for r in valid_results]
        y_pred = [r['gemini_response'] for r in valid_results]
        
        # Calculate accuracy
        correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
        accuracy = correct / len(valid_results) if valid_results else 0
        
        # Calculate per-class metrics
        unique_labels = set(y_true + y_pred)
        class_metrics = {}
        
        for label in unique_labels:
            tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
            fp = sum(1 for t, p in zip(y_true, y_pred) if t != label and p == label)
            fn = sum(1 for t, p in zip(y_true, y_pred) if t == label and p != label)
            
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
            
            class_metrics[label] = {
                'precision': precision,
                'recall': recall,
                'f1': f1,
                'support': sum(1 for t in y_true if t == label)
            }
        
        # Calculate weighted averages
        total_support = len(y_true)
        weighted_precision = sum(m['precision'] * m['support'] for m in class_metrics.values()) / total_support
        weighted_recall = sum(m['recall'] * m['support'] for m in class_metrics.values()) / total_support
        weighted_f1 = sum(m['f1'] * m['support'] for m in class_metrics.values()) / total_support
        
        metrics = {
            'accuracy': accuracy * 100,
            'precision': weighted_precision * 100,
            'recall': weighted_recall * 100,
            'f1_score': weighted_f1 * 100,
            'total_valid': len(valid_results),
            'total_tested': stats['total'],
            'per_class': {k: {kk: vv * 100 if kk != 'support' else vv 
                              for kk, vv in v.items()} 
                          for k, v in class_metrics.items()}
        }
        
        logger.info(f"Metrics - Accuracy: {accuracy*100:.2f}%, F1: {weighted_f1*100:.2f}%")
    else:
        metrics = {
            'accuracy': 0,
            'precision': 0,
            'recall': 0,
            'f1_score': 0,
            'total_valid': 0,
            'total_tested': stats['total']
        }
    
    # Save statistics
    stats_file = os.path.join(output_dir, f'{q_type.lower()}_statistics.json')
    
    # Convert defaultdict to regular dict for JSON serialization
    stats_json = {
        'total': stats['total'],
        'correct': stats['correct'],
        'incorrect': stats['incorrect'],
        'no_response': stats['no_response'],
        'accuracy': stats['correct'] / stats['total'] * 100,
        'metrics': metrics,
        'by_hop': {str(k): dict(v) for k, v in stats['by_hop'].items()},
        'by_variant': {k: dict(v) for k, v in stats['by_variant'].items()}
    }
    
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats_json, f, ensure_ascii=False, indent=2)
    print(f"\nSaved statistics to {stats_file}")
    
    return stats, metrics, valid_results


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Test Gemini accuracy on generated questions')
    parser.add_argument('--data_dir', default='chatbot/Q_and_A/output',
                       help='Directory containing question files')
    parser.add_argument('--output_dir', default='chatbot/test_with_Gemini/results',
                       help='Directory to save test results')
    parser.add_argument('--mcq', action='store_true', help='Test MCQ questions')
    parser.add_argument('--tf', action='store_true', help='Test TRUE_FALSE questions')
    parser.add_argument('--sample', type=int, default=None,
                       help='Sample size (default: test all)')
    
    args = parser.parse_args()
    
    # If neither specified, test both
    if not args.mcq and not args.tf:
        args.mcq = True
        args.tf = True
    
    all_metrics = {}
    all_results = []
    
    if args.mcq:
        stats_mcq, metrics_mcq, results_mcq = test_questions(args.data_dir, args.output_dir, 'MCQ', args.sample)
        all_metrics['MCQ'] = metrics_mcq
        all_results.extend(results_mcq)
    
    if args.tf:
        stats_tf, metrics_tf, results_tf = test_questions(args.data_dir, args.output_dir, 'TRUE_FALSE', args.sample)
        all_metrics['TRUE_FALSE'] = metrics_tf
        all_results.extend(results_tf)
    
    # Calculate combined metrics
    if all_results:
        y_true = [r['ground_truth'] for r in all_results]
        y_pred = [r['gemini_response'] for r in all_results]
        
        # Calculate accuracy
        correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
        accuracy = correct / len(all_results)
        
        # Calculate per-class metrics
        unique_labels = set(y_true + y_pred)
        class_metrics = {}
        
        for label in unique_labels:
            tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
            fp = sum(1 for t, p in zip(y_true, y_pred) if t != label and p == label)
            fn = sum(1 for t, p in zip(y_true, y_pred) if t == label and p != label)
            
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
            
            class_metrics[label] = {
                'precision': precision,
                'recall': recall,
                'f1': f1,
                'support': sum(1 for t in y_true if t == label)
            }
        
        # Calculate weighted averages
        total_support = len(y_true)
        weighted_precision = sum(m['precision'] * m['support'] for m in class_metrics.values()) / total_support
        weighted_recall = sum(m['recall'] * m['support'] for m in class_metrics.values()) / total_support
        weighted_f1 = sum(m['f1'] * m['support'] for m in class_metrics.values()) / total_support
        
        all_metrics['COMBINED'] = {
            'accuracy': accuracy * 100,
            'precision': weighted_precision * 100,
            'recall': weighted_recall * 100,
            'f1_score': weighted_f1 * 100,
            'total_valid': len(all_results)
        }
    
    # Write metrics to txt file
    metrics_file = os.path.join(args.output_dir, 'metrics_summary.txt')
    
    with open(metrics_file, 'w', encoding='utf-8') as f:
        f.write("="*70 + "\n")
        f.write("GEMINI MODEL EVALUATION METRICS\n")
        f.write("="*70 + "\n\n")
        
        for q_type, metrics in all_metrics.items():
            f.write(f"\n{'='*70}\n")
            f.write(f"{q_type} QUESTIONS\n")
            f.write(f"{'='*70}\n")
            
            # Overall statistics
            total_tested = metrics.get('total_tested', metrics.get('total_valid', 0))
            total_valid = metrics.get('total_valid', 0)
            no_response = total_tested - total_valid
            
            f.write(f"Total Tested:          {total_tested}\n")
            f.write(f"Valid Responses:       {total_valid}\n")
            f.write(f"No Response:           {no_response}\n")
            f.write(f"\nPerformance Metrics:\n")
            f.write(f"  Accuracy:            {metrics.get('accuracy', 0):.2f}%\n")
            f.write(f"  Precision (weighted): {metrics.get('precision', 0):.2f}%\n")
            f.write(f"  Recall (weighted):    {metrics.get('recall', 0):.2f}%\n")
            f.write(f"  F1-Score (weighted):  {metrics.get('f1_score', 0):.2f}%\n")
            
            # Per-class metrics if available
            if 'per_class' in metrics:
                f.write(f"\nPer-Class Metrics:\n")
                for label, class_metrics in sorted(metrics['per_class'].items()):
                    f.write(f"  {label}:\n")
                    f.write(f"    Support:   {class_metrics.get('support', 0)}\n")
                    f.write(f"    Precision: {class_metrics.get('precision', 0):.2f}%\n")
                    f.write(f"    Recall:    {class_metrics.get('recall', 0):.2f}%\n")
                    f.write(f"    F1-Score:  {class_metrics.get('f1', 0):.2f}%\n")
        
        f.write(f"\n{'='*70}\n")
        f.write("Generated at: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n")
        f.write("="*70 + "\n")
    
    print(f"\n✓ Metrics summary saved to: {metrics_file}")
    print("\n✓ Testing complete!")


if __name__ == '__main__':
    main()

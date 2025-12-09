"""
Test accuracy of Political Chatbot on generated questions.
Compare chatbot's answers with ground truth answers.
"""

import os
import sys
import json
import pandas as pd
from tqdm import tqdm
import time
from collections import defaultdict
import logging
from datetime import datetime
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from chatbot.graph.workflow import run_chatbot_workflow


# Setup logging
def setup_logging(output_dir):
    """Setup logging to file and console."""
    os.makedirs(output_dir, exist_ok=True)
    
    log_file = os.path.join(output_dir, 'test_accuracy.log')
    
    # Create logger
    logger = logging.getLogger('test_accuracy')
    logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers
    logger.handlers = []
    
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


def ask_chatbot(question, history, logger):
    """Ask chatbot a question and get the answer."""
    logger.debug(f"Asking chatbot: {question[:100]}...")
    
    try:
        result = run_chatbot_workflow(question, history)
        assistant_output = result.get("assistant_output", "")
        new_history = result.get("history", history)
        
        logger.debug(f"Chatbot response: {assistant_output[:200]}...")
        
        return assistant_output.strip(), new_history
        
    except Exception as e:
        logger.error(f"Error asking chatbot: {str(e)[:200]}")
        return None, history


def extract_answer_from_response(response, q_type):
    """Extract answer from chatbot's response."""
    if not response:
        return None
    
    response_lower = response.lower()
    
    if q_type == 'MCQ':
        # Strategy 1: Check if response starts with a single letter (A/B/C/D)
        # This handles cases like "C. Lê Quang Mạnh - Vũ Quang Minh..."
        first_char = response.strip()[0].upper() if response.strip() else None
        if first_char in ['A', 'B', 'C', 'D']:
            # Verify it's followed by ., ), or space to avoid false positives
            if len(response) > 1 and response[1] in ['.', ')', ' ', ':']:
                return first_char
        
        # Strategy 2: Look for pattern "[X]" where X is A-D
        bracket_match = re.search(r'\[([A-D])\]', response, re.IGNORECASE)
        if bracket_match:
            return bracket_match.group(1).upper()
        
        # Strategy 3: Look for "Đáp án: X" or "Đáp án X"
        answer_patterns = [
            r'đáp án:\s*([A-D])',
            r'đáp án\s+([A-D])',
            r'chọn\s+([A-D])',
            r'lựa chọn\s+([A-D])',
            r'\b([A-D])\s*\.',  # Letter followed by period
        ]
        
        for pattern in answer_patterns:
            match = re.search(pattern, response_lower)
            if match:
                return match.group(1).upper()
        
        # Strategy 4: Check first line for standalone letter
        first_line = response.split('\n')[0].strip()
        if first_line in ['A', 'B', 'C', 'D', 'a', 'b', 'c', 'd']:
            return first_line.upper()
        
        # Strategy 5: Look for option in last part
        last_part = response_lower[-200:]
        for option in ['A', 'B', 'C', 'D']:
            if f'[{option.lower()}]' in last_part or f'đáp án {option.lower()}' in last_part:
                return option
                
    else:  # TRUE_FALSE
        # Strategy 1: Direct answer at start
        first_line = response.split('\n')[0].strip()
        if first_line in ['Đúng', 'Sai', 'Không có dữ kiện', 'Không đủ thông tin']:
            return first_line
        
        # Strategy 2: Look for conclusive patterns
        conclusive_patterns = [
            (r'đáp án:\s*(đúng|sai|không có dữ kiện)', 1),
            (r'câu trả lời là\s*(đúng|sai|không có dữ kiện)', 1),
            (r'kết luận:\s*(đúng|sai|không có dữ kiện)', 1),
        ]
        
        for pattern, group in conclusive_patterns:
            match = re.search(pattern, response_lower)
            if match:
                answer = match.group(group).strip()
                if 'đúng' in answer:
                    return 'Đúng'
                elif 'sai' in answer:
                    return 'Sai'
                elif 'không' in answer:
                    return 'Không có dữ kiện'
        
        # Strategy 3: Count occurrences in last part
        last_part = response_lower[-300:]
        
        if 'đúng' in last_part and 'sai' not in last_part:
            return 'Đúng'
        elif 'sai' in last_part and 'đúng' not in last_part:
            return 'Sai'
        elif 'không có dữ kiện' in last_part or 'không đủ thông tin' in last_part:
            return 'Không có dữ kiện'
        
        # Strategy 4: Fallback - count total occurrences
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
    Test questions with chatbot and compare with ground truth.
    
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
    history = []  # Maintain conversation history
    
    # Test each question
    print(f"\nTesting questions...")
    for idx, row in tqdm(data.iterrows(), total=len(data), desc="Processing"):
        question = row['question']
        ground_truth = row['answer']
        hop_count = row['hop_count']
        variant_type = get_variant_type(row)
        
        logger.info(f"Testing question {row['id']} (hop={hop_count}, type={variant_type})")
        
        # Ask chatbot
        response, history = ask_chatbot(question, history, logger)
        
        # Extract answer from response
        answer = extract_answer_from_response(response, q_type) if response else None
        
        logger.debug(f"Extracted answer: {answer}, Ground truth: {ground_truth}")
        
        # Compare
        is_correct = (answer == ground_truth) if answer else False
        
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
            'chatbot_response': response,
            'extracted_answer': answer,
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
        
        # Small delay to avoid overwhelming the system
        time.sleep(0.5)
    
    # Save final results
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
        accuracy = hop_stats['correct'] / hop_stats['total'] * 100 if hop_stats['total'] > 0 else 0
        print(f"{hop}-hop: {hop_stats['correct']}/{hop_stats['total']} correct ({accuracy:.2f}%)")
    
    print(f"\n{'='*60}")
    print("STATISTICS BY VARIANT TYPE")
    print(f"{'='*60}")
    for variant in sorted(stats['by_variant'].keys()):
        variant_stats = stats['by_variant'][variant]
        accuracy = variant_stats['correct'] / variant_stats['total'] * 100 if variant_stats['total'] > 0 else 0
        print(f"{variant}: {variant_stats['correct']}/{variant_stats['total']} correct ({accuracy:.2f}%)")
    
    # Calculate metrics
    valid_results = [r for r in results if r['extracted_answer'] is not None]
    
    metrics = {}
    if valid_results:
        y_true = [r['ground_truth'] for r in valid_results]
        y_pred = [r['extracted_answer'] for r in valid_results]
        
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
    
    parser = argparse.ArgumentParser(description='Test Chatbot accuracy on generated questions')
    parser.add_argument('--data_dir', default='chatbot/Q_and_A/output_filtered',
                       help='Directory containing question files')
    parser.add_argument('--output_dir', default='chatbot/test_chatbot/results',
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
        y_pred = [r['extracted_answer'] for r in all_results]
        
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
        f.write("POLITICAL CHATBOT EVALUATION METRICS\n")
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

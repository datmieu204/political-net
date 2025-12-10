"""
Calculate detailed metrics by hop_count from existing test results.
"""

import json
import os
from collections import defaultdict


def calculate_metrics(y_true, y_pred):
    """Calculate precision, recall, F1 for given predictions."""
    if not y_true or not y_pred:
        return None
    
    # Calculate accuracy
    correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    accuracy = correct / len(y_true) * 100 if y_true else 0
    
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
            'precision': precision * 100,
            'recall': recall * 100,
            'f1': f1 * 100,
            'support': sum(1 for t in y_true if t == label)
        }
    
    # Weighted averages
    total_support = len(y_true)
    weighted_precision = sum(m['precision'] * m['support'] / 100 for m in class_metrics.values()) / total_support * 100
    weighted_recall = sum(m['recall'] * m['support'] / 100 for m in class_metrics.values()) / total_support * 100
    weighted_f1 = sum(m['f1'] * m['support'] / 100 for m in class_metrics.values()) / total_support * 100
    
    return {
        'accuracy': accuracy,
        'precision': weighted_precision,
        'recall': weighted_recall,
        'f1_score': weighted_f1,
        'total': len(y_true),
        'correct': correct,
        'per_class': class_metrics
    }


def calculate_hop_metrics(results_file, output_file):
    """Calculate metrics by hop_count from results file."""
    print(f"Loading results from {results_file}...")
    
    with open(results_file, 'r', encoding='utf-8') as f:
        results = json.load(f)
    
    print(f"Total results: {len(results)}")
    
    # Group by hop_count
    by_hop = defaultdict(lambda: {'y_true': [], 'y_pred': [], 'total': 0, 'correct': 0})
    
    for result in results:
        hop = result['hop_count']
        ground_truth = result['ground_truth']
        extracted_answer = result.get('extracted_answer')
        is_correct = result['is_correct']
        
        by_hop[hop]['total'] += 1
        if is_correct:
            by_hop[hop]['correct'] += 1
        
        # Only include valid responses for metric calculation
        if extracted_answer is not None:
            by_hop[hop]['y_true'].append(ground_truth)
            by_hop[hop]['y_pred'].append(extracted_answer)
    
    # Calculate metrics for each hop
    hop_metrics = {}
    
    print(f"\n{'='*60}")
    print("METRICS BY HOP COUNT")
    print(f"{'='*60}")
    
    for hop in sorted(by_hop.keys()):
        hop_data = by_hop[hop]
        accuracy = hop_data['correct'] / hop_data['total'] * 100 if hop_data['total'] > 0 else 0
        
        print(f"\n{hop}-hop:")
        print(f"  Total: {hop_data['total']}")
        print(f"  Correct: {hop_data['correct']}")
        print(f"  Accuracy: {accuracy:.2f}%")
        
        # Calculate detailed metrics
        metrics = calculate_metrics(hop_data['y_true'], hop_data['y_pred'])
        
        if metrics:
            print(f"  Precision: {metrics['precision']:.2f}%")
            print(f"  Recall: {metrics['recall']:.2f}%")
            print(f"  F1 Score: {metrics['f1_score']:.2f}%")
            
            print(f"\n  Per-class metrics:")
            for label, label_metrics in sorted(metrics['per_class'].items()):
                print(f"    {label}:")
                print(f"      Precision: {label_metrics['precision']:.2f}%")
                print(f"      Recall: {label_metrics['recall']:.2f}%")
                print(f"      F1: {label_metrics['f1']:.2f}%")
                print(f"      Support: {label_metrics['support']}")
            
            hop_metrics[str(hop)] = metrics
    
    # Save to file
    output = {
        'by_hop': hop_metrics
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print(f"Saved metrics to {output_file}")
    print(f"{'='*60}")
    
    return hop_metrics


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Calculate metrics by hop_count from test results')
    parser.add_argument('--results_dir', default='chatbot/test_chatbot/results',
                       help='Directory containing test result files')
    parser.add_argument('--mcq', action='store_true', help='Process MCQ results')
    parser.add_argument('--tf', action='store_true', help='Process TRUE_FALSE results')
    
    args = parser.parse_args()
    
    # If neither specified, process both
    if not args.mcq and not args.tf:
        args.mcq = True
        args.tf = True
    
    if args.mcq:
        mcq_results = os.path.join(args.results_dir, 'mcq_test_results.json')
        mcq_output = os.path.join(args.results_dir, 'mcq_hop_metrics.json')
        
        if os.path.exists(mcq_results):
            print("\nProcessing MCQ results...")
            calculate_hop_metrics(mcq_results, mcq_output)
        else:
            print(f"MCQ results file not found: {mcq_results}")
    
    if args.tf:
        tf_results = os.path.join(args.results_dir, 'true_false_test_results.json')
        tf_output = os.path.join(args.results_dir, 'true_false_hop_metrics.json')
        
        if os.path.exists(tf_results):
            print("\nProcessing TRUE_FALSE results...")
            calculate_hop_metrics(tf_results, tf_output)
        else:
            print(f"TRUE_FALSE results file not found: {tf_results}")


if __name__ == '__main__':
    main()

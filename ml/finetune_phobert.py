# ml/finetune_phobert.py

"""
Fine-tune PhoBERT (vinai/phobert-base-v2) cho Named Entity Recognition
trên dữ liệu chính trị gia Việt Nam

Architecture:
- Base model: vinai/phobert-base-v2 (RoBERTa for Vietnamese)
- Task: Token Classification (NER)
- Additional head: Linear layer cho relation extraction
"""

import os
import json
import torch
import numpy as np
from tqdm import tqdm
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass

from transformers import (
    AutoTokenizer,
    AutoModelForTokenClassification,
    TrainingArguments,
    Trainer,
    DataCollatorForTokenClassification
)
from datasets import Dataset, DatasetDict
from sklearn.model_selection import train_test_split
from seqeval.metrics import classification_report, f1_score, precision_score, recall_score

from utils._logger import get_logger

logger = get_logger("ml.finetune_phobert", log_file="logs/ml/finetune_phobert.log")


# Entity labels (BIO tagging)
ENTITY_LABELS = [
    "O",  # Outside
    "B-POSITION", "I-POSITION",
    "B-LOCATION", "I-LOCATION",
    "B-ORGANIZATION", "I-ORGANIZATION",
    "B-SCHOOL", "I-SCHOOL",
    "B-MILITARY_UNIT", "I-MILITARY_UNIT",
    "B-MILITARY_RANK", "I-MILITARY_RANK",
    "B-AWARD", "I-AWARD",
    "B-CAMPAIGN", "I-CAMPAIGN",
    "B-ACADEMIC_TITLE", "I-ACADEMIC_TITLE",
    "B-PERSON", "I-PERSON",
    "B-DATE", "I-DATE",
    "B-STATUS", "I-STATUS"
]

LABEL2ID = {label: i for i, label in enumerate(ENTITY_LABELS)}
ID2LABEL = {i: label for label, i in LABEL2ID.items()}


class NERDataProcessor:
    """
    Xử lý dữ liệu từ JSONL format sang format cho PhoBERT
    """
    
    def __init__(self, tokenizer):
        self.tokenizer = tokenizer
    
    def convert_to_bio(self, text: str, entities: List[Dict]) -> List[str]:
        """
        Convert entities to BIO tags for each character
        
        Args:
            text: Input text
            entities: List of entities with start, end, label
        
        Returns:
            List of BIO tags for each character
        """
        # Initialize all as O
        char_labels = ["O"] * len(text)
        
        # Sort entities by start position
        sorted_entities = sorted(entities, key=lambda x: x["start"])
        
        for ent in sorted_entities:
            start = ent["start"]
            end = ent["end"]
            label = ent["label"]
            
            if start >= len(text) or end > len(text):
                logger.warning(f"Entity out of bounds: {ent}")
                continue
            
            # First token gets B- tag
            char_labels[start] = f"B-{label}"
            
            # Subsequent tokens get I- tag
            for i in range(start + 1, end):
                char_labels[i] = f"I-{label}"
        
        return char_labels
    
    def align_labels_with_tokens(self, text: str, char_labels: List[str], 
                                 encoding) -> List[int]:
        """
        Align character-level labels with wordpiece tokens
        
        Strategy:
        - First token of a word inherits the label
        - Subsequent subword tokens get -100 (ignored in loss)
        """
        labels = []
        
        for token_idx in range(len(encoding.tokens())):
            # Get character span for this token
            span = encoding.token_to_chars(token_idx)
            
            if span is None:
                # Special tokens (CLS, SEP, PAD)
                labels.append(-100)
            else:
                start_char = span.start
                
                # Get label for first character of token
                char_label = char_labels[start_char]
                label_id = LABEL2ID.get(char_label, LABEL2ID["O"])
                labels.append(label_id)
        
        return labels
    
    def process_sample(self, sample: Dict) -> Dict:
        """
        Process one sample: text + entities -> tokenized input + labels
        """
        text = sample["text"]
        entities = sample["entities"]
        
        # Step 1: Convert entities to character-level BIO tags
        char_labels = self.convert_to_bio(text, entities)
        
        # Step 2: Tokenize text
        encoding = self.tokenizer(
            text,
            truncation=True,
            max_length=512,
            return_offsets_mapping=True
        )
        
        # Step 3: Align labels with tokens
        labels = self.align_labels_with_tokens(text, char_labels, encoding)
        
        return {
            "input_ids": encoding["input_ids"],
            "attention_mask": encoding["attention_mask"],
            "labels": labels
        }
    
    def load_dataset(self, jsonl_file: str, test_size: float = 0.2) -> DatasetDict:
        """
        Load JSONL file and convert to HuggingFace Dataset
        
        Returns:
            DatasetDict with train/test splits
        """
        logger.info(f"Loading dataset from {jsonl_file}")
        
        # Read JSONL
        samples = []
        with open(jsonl_file, 'r', encoding='utf-8') as f:
            for line in f:
                samples.append(json.loads(line))
        
        logger.info(f"Loaded {len(samples)} samples")
        
        # Process all samples
        processed = []
        for sample in tqdm(samples, desc="Processing samples"):
            try:
                processed_sample = self.process_sample(sample)
                processed_sample["id"] = sample["id"]
                processed_sample["name"] = sample["name"]
                processed.append(processed_sample)
            except Exception as e:
                logger.error(f"Error processing {sample['id']}: {e}")
        
        logger.info(f"Successfully processed {len(processed)} samples")
        
        # Train/test split
        train_samples, test_samples = train_test_split(
            processed, 
            test_size=test_size, 
            random_state=42
        )
        
        # Convert to HuggingFace Dataset
        train_dataset = Dataset.from_list(train_samples)
        test_dataset = Dataset.from_list(test_samples)
        
        dataset_dict = DatasetDict({
            "train": train_dataset,
            "test": test_dataset
        })
        
        logger.info(f"Train: {len(train_dataset)}, Test: {len(test_dataset)}")
        
        return dataset_dict


def compute_metrics(eval_pred):
    """
    Compute NER metrics using seqeval
    """
    predictions, labels = eval_pred
    predictions = np.argmax(predictions, axis=2)
    
    # Remove ignored index (special tokens)
    true_predictions = [
        [ID2LABEL[p] for (p, l) in zip(prediction, label) if l != -100]
        for prediction, label in zip(predictions, labels)
    ]
    true_labels = [
        [ID2LABEL[l] for (p, l) in zip(prediction, label) if l != -100]
        for prediction, label in zip(predictions, labels)
    ]
    
    # Compute metrics
    f1 = f1_score(true_labels, true_predictions)
    precision = precision_score(true_labels, true_predictions)
    recall = recall_score(true_labels, true_predictions)
    
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1
    }


class PhoBERTFineTuner:
    
    def __init__(self, model_name: str = "vinai/phobert-base-v2"):
        self.model_name = model_name
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.processor = NERDataProcessor(self.tokenizer)
        
        logger.info(f"Initialized with model: {model_name}")
    
    def train(self, 
              training_data_file: str,
              output_dir: str = "ml/models/phobert-ner",
              num_epochs: int = 5,
              batch_size: int = 8,
              learning_rate: float = 2e-5):
        """
        Fine-tune PhoBERT for NER
        """
        logger.info("Starting training...")
        
        # Load and process dataset
        dataset = self.processor.load_dataset(training_data_file)
        
        # Load model
        model = AutoModelForTokenClassification.from_pretrained(
            self.model_name,
            num_labels=len(ENTITY_LABELS),
            id2label=ID2LABEL,
            label2id=LABEL2ID
        )
        
        # Training arguments
        training_args = TrainingArguments(
            output_dir=output_dir,
            evaluation_strategy="epoch",
            save_strategy="epoch",
            learning_rate=learning_rate,
            per_device_train_batch_size=batch_size,
            per_device_eval_batch_size=batch_size,
            num_train_epochs=num_epochs,
            weight_decay=0.01,
            logging_steps=10,
            load_best_model_at_end=True,
            metric_for_best_model="f1",
            push_to_hub=False,
            report_to=["tensorboard"]
        )
        
        # Data collator
        data_collator = DataCollatorForTokenClassification(
            tokenizer=self.tokenizer
        )
        
        # Trainer
        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=dataset["train"],
            eval_dataset=dataset["test"],
            tokenizer=self.tokenizer,
            data_collator=data_collator,
            compute_metrics=compute_metrics
        )
        
        # Train
        logger.info("Training started...")
        train_result = trainer.train()
        
        # Save model
        trainer.save_model(output_dir)
        self.tokenizer.save_pretrained(output_dir)
        
        # Evaluate
        logger.info("Evaluating on test set...")
        metrics = trainer.evaluate()
        
        # Save metrics
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        metrics_file = os.path.join(output_dir, f"metrics_{timestamp}.json")
        with open(metrics_file, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, indent=2)
        
        logger.info(f"Training complete. Model saved to: {output_dir}")
        logger.info(f"Metrics: {metrics}")
        
        # Generate detailed report
        predictions = trainer.predict(dataset["test"])
        pred_labels = np.argmax(predictions.predictions, axis=2)
        
        true_predictions = [
            [ID2LABEL[p] for (p, l) in zip(prediction, label) if l != -100]
            for prediction, label in zip(pred_labels, predictions.label_ids)
        ]
        true_labels = [
            [ID2LABEL[l] for (p, l) in zip(prediction, label) if l != -100]
            for prediction, label in zip(pred_labels, predictions.label_ids)
        ]
        
        report = classification_report(true_labels, true_predictions)
        
        report_file = os.path.join(output_dir, f"classification_report_{timestamp}.txt")
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"Classification report saved to: {report_file}")
        print("\n" + "="*60)
        print("TRAINING COMPLETE")
        print("="*60)
        print(report)
        print("="*60)
        
        return trainer, metrics


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Fine-tune PhoBERT for NER")
    parser.add_argument(
        "--data", "-d",
        type=str,
        required=True,
        help="Path to training data JSONL file"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="ml/models/phobert-ner",
        help="Output directory for trained model"
    )
    parser.add_argument(
        "--epochs", "-e",
        type=int,
        default=5,
        help="Number of training epochs"
    )
    parser.add_argument(
        "--batch-size", "-b",
        type=int,
        default=8,
        help="Training batch size"
    )
    parser.add_argument(
        "--learning-rate", "-lr",
        type=float,
        default=2e-5,
        help="Learning rate"
    )
    
    args = parser.parse_args()
    
    fine_tuner = PhoBERTFineTuner()
    fine_tuner.train(
        training_data_file=args.data,
        output_dir=args.output,
        num_epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate
    )

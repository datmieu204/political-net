# ml/inference_phobert.py

"""
Inference script sử dụng PhoBERT đã fine-tune
Thay thế LLM (Gemini) trong extract_from_summary
"""

import os
import json
import torch
from typing import Dict, List, Tuple
from transformers import (
    AutoTokenizer,
    AutoModelForTokenClassification,
    pipeline
)

from utils._logger import get_logger

logger = get_logger("ml.inference_phobert", log_file="logs/ml/inference_phobert.log")


class PhoBERTExtractor:
    """
    Trích xuất entities từ văn bản tiểu sử chính trị gia
    Sử dụng PhoBERT đã fine-tune
    """
    
    def __init__(self, model_path: str = "ml/models/phobert-ner"):
        """
        Args:
            model_path: Path to fine-tuned model
        """
        logger.info(f"Loading model from {model_path}")
        
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForTokenClassification.from_pretrained(model_path)
        
        # NER pipeline
        self.ner_pipeline = pipeline(
            "ner",
            model=self.model,
            tokenizer=self.tokenizer,
            aggregation_strategy="simple",  # Merge B-/I- tokens
            device=0 if torch.cuda.is_available() else -1
        )
        
        logger.info(f"Model loaded. Using device: {'cuda' if torch.cuda.is_available() else 'cpu'}")
    
    def extract_entities(self, text: str) -> List[Dict]:
        """
        Extract entities from text
        
        Returns:
            List of entities with format:
            [
                {
                    "text": "Bí thư Tỉnh ủy Hà Nội",
                    "label": "POSITION",
                    "start": 10,
                    "end": 35,
                    "score": 0.95
                },
                ...
            ]
        """
        # Run NER
        entities = self.ner_pipeline(text)
        
        # Format results
        formatted = []
        for ent in entities:
            formatted.append({
                "text": ent["word"],
                "label": ent["entity_group"],
                "start": ent["start"],
                "end": ent["end"],
                "score": ent["score"]
            })
        
        return formatted
    
    def group_entities_by_type(self, entities: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Group entities by their type
        
        Returns:
            {
                "POSITION": [...],
                "LOCATION": [...],
                ...
            }
        """
        grouped = {}
        
        for ent in entities:
            label = ent["label"]
            if label not in grouped:
                grouped[label] = []
            grouped[label].append(ent)
        
        return grouped
    
    def extract_from_summary(self, summary: str, politician_name: str, 
                           politician_id: str) -> Dict:
        """
        Main extraction function - THAY THẾ cho LLM-based extraction
        
        Format giống với enrich_neo4j.py để tương thích
        
        Returns:
            {
                "positions": [...],
                "locations": [...],
                "alma_mater": [...],
                "military_careers": [...],
                "military_ranks": [...],
                "awards": [...],
                "campaigns": [...],
                "academic_titles": [...],
                "succession_relations": []
            }
        """
        # Extract all entities
        entities = self.extract_entities(summary)
        grouped = self.group_entities_by_type(entities)
        
        # Convert to output format
        result = {
            "positions": [],
            "locations": [],
            "alma_mater": [],
            "military_careers": [],
            "military_ranks": [],
            "awards": [],
            "campaigns": [],
            "academic_titles": [],
            "succession_relations": []
        }
        
        # Positions
        for ent in grouped.get("POSITION", []):
            result["positions"].append({
                "name": ent["text"],
                "organization": "",  # TODO: Extract from context
                "term_start": "",
                "term_end": "",
                "status": "",
                "reason": ""
            })
        
        # Locations
        for ent in grouped.get("LOCATION", []):
            # Determine relation from context
            relation = "BORN_AT"  # Default
            
            # Check context for "sinh" or "mất"
            start = max(0, ent["start"] - 50)
            end = min(len(summary), ent["end"] + 50)
            context = summary[start:end].lower()
            
            if "mất" in context or "qua đời" in context:
                relation = "DIED_AT"
            
            result["locations"].append({
                "name": ent["text"],
                "relation": relation
            })
        
        # Schools (AlmaMater)
        for ent in grouped.get("SCHOOL", []):
            result["alma_mater"].append({
                "name": ent["text"]
            })
        
        # Military units
        for ent in grouped.get("MILITARY_UNIT", []):
            result["military_careers"].append({
                "name": ent["text"],
                "year_start": "",
                "year_end": ""
            })
        
        # Military ranks
        for ent in grouped.get("MILITARY_RANK", []):
            result["military_ranks"].append({
                "name": ent["text"]
            })
        
        # Awards
        for ent in grouped.get("AWARD", []):
            result["awards"].append({
                "name": ent["text"],
                "year": ""
            })
        
        # Campaigns
        for ent in grouped.get("CAMPAIGN", []):
            result["campaigns"].append({
                "name": ent["text"],
                "year": ""
            })
        
        # Academic titles
        for ent in grouped.get("ACADEMIC_TITLE", []):
            result["academic_titles"].append({
                "name": ent["text"]
            })
        
        # Succession relations (TODO: Implement relation extraction)
        # This requires more sophisticated NLP (relation extraction model)
        # For now, leave empty
        
        logger.info(f"Extracted from {politician_name}: "
                   f"{len(result['positions'])} positions, "
                   f"{len(result['locations'])} locations, "
                   f"{len(result['alma_mater'])} schools")
        
        return result


# Standalone test
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test PhoBERT inference")
    parser.add_argument(
        "--model", "-m",
        type=str,
        default="ml/models/phobert-ner",
        help="Path to fine-tuned model"
    )
    parser.add_argument(
        "--text", "-t",
        type=str,
        help="Text to extract from (or use --file)"
    )
    parser.add_argument(
        "--file", "-f",
        type=str,
        help="JSON file with politician data"
    )
    parser.add_argument(
        "--id", "-i",
        type=str,
        help="Politician ID to test (if using --file)"
    )
    
    args = parser.parse_args()
    
    extractor = PhoBERTExtractor(model_path=args.model)
    
    if args.text:
        # Test with raw text
        entities = extractor.extract_entities(args.text)
        print("\nExtracted entities:")
        for ent in entities:
            print(f"  [{ent['label']}] {ent['text']} (score: {ent['score']:.2f})")
    
    elif args.file:
        # Test with politician data
        with open(args.file, 'r', encoding='utf-8') as f:
            politicians = json.load(f)
        
        # Find politician
        target = None
        for p in politicians:
            if f"pol{p['id']}" == args.id or p['title'] == args.id:
                target = p
                break
        
        if not target:
            print(f"Politician not found: {args.id}")
        else:
            pol_id = f"pol{target['id']}"
            pol_name = target['title']
            summary = target['summary']
            
            print(f"\nExtracting from: {pol_name} ({pol_id})")
            print(f"Summary length: {len(summary)} chars\n")
            
            result = extractor.extract_from_summary(summary, pol_name, pol_id)
            
            print("\n" + "="*60)
            print("EXTRACTION RESULTS")
            print("="*60)
            print(json.dumps(result, ensure_ascii=False, indent=2))
    
    else:
        print("Please provide --text or --file")

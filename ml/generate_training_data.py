# ml/generate_training_data.py

"""
Script tự động sinh dataset huấn luyện từ dữ liệu có sẵn
Sử dụng LLM (Gemini) để tạo annotations cho việc fine-tune PhoBERT

Strategy:
1. Sử dụng LLM để sinh annotations cho một phần dữ liệu (200-300 samples)
2. Annotations bao gồm:
   - Named Entity Recognition (NER): Position, Location, Award, etc.
   - Span extraction: trích xuất vị trí chính xác của entities trong text
3. Format: JSON Lines với schema phù hợp cho PhoBERT NER
"""

import os
import json
import time
from tqdm import tqdm
from datetime import datetime
from typing import Dict, List, Tuple
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

from utils.config import settings
from utils._logger import get_logger
from utils.api_key_rotator import get_api_key_rotator

logger = get_logger("ml.generate_training_data", log_file="logs/ml/generate_training_data.log")


# Entity types theo schema
ENTITY_TYPES = {
    "POSITION": "Chức vụ chính trị",
    "LOCATION": "Địa danh (nơi sinh, nơi mất)",
    "ORGANIZATION": "Tổ chức, cơ quan",
    "SCHOOL": "Trường học, học viện",
    "MILITARY_UNIT": "Đơn vị quân đội/công an",
    "MILITARY_RANK": "Cấp bậc quân đội/công an",
    "AWARD": "Huân chương, giải thưởng",
    "CAMPAIGN": "Chiến dịch quân sự",
    "ACADEMIC_TITLE": "Học hàm, học vị",
    "PERSON": "Tên người (cho succession relations)",
    "DATE": "Thời gian (năm, ngày tháng)",
    "STATUS": "Trạng thái (bị cách chức, miễn nhiệm...)"
}


ANNOTATION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "entities": {
            "type": "ARRAY",
            "description": "Danh sách các entity được trích xuất từ văn bản",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "text": {"type": "STRING", "description": "Văn bản chính xác của entity"},
                    "start": {"type": "INTEGER", "description": "Vị trí bắt đầu trong văn bản (character index)"},
                    "end": {"type": "INTEGER", "description": "Vị trí kết thúc trong văn bản (character index)"},
                    "label": {"type": "STRING", "description": "Loại entity: POSITION, LOCATION, ORGANIZATION, SCHOOL, MILITARY_UNIT, MILITARY_RANK, AWARD, CAMPAIGN, ACADEMIC_TITLE, PERSON, DATE, STATUS"},
                    "metadata": {"type": "OBJECT", "description": "Thông tin bổ sung (tùy chọn)"}
                },
                "required": ["text", "start", "end", "label"]
            }
        },
        "relations": {
            "type": "ARRAY",
            "description": "Quan hệ giữa các entity",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "head": {"type": "INTEGER", "description": "Index của entity đầu trong danh sách entities"},
                    "tail": {"type": "INTEGER", "description": "Index của entity cuối trong danh sách entities"},
                    "relation": {"type": "STRING", "description": "Loại quan hệ: SERVED_AS, BORN_AT, DIED_AT, ALUMNUS_OF, HAS_RANK, AWARDED, FOUGHT_IN, HAS_ACADEMIC_TITLE, SUCCEEDED, PRECEDED"}
                },
                "required": ["head", "tail", "relation"]
            }
        }
    }
}


class TrainingDataGenerator:
    
    def __init__(self):
        self.api_rotator = get_api_key_rotator()
        logger.info(f"Using API key: {self.api_rotator.get_current_key_name()}")
        
        self.model = genai.GenerativeModel(
            model_name="gemini-2.5-flash-lite",
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": ANNOTATION_SCHEMA,
                "temperature": 0.1
            }
        )
        self.request_interval = 4.0
        self.last_request_time = 0
    
    def annotate_text(self, summary: str, politician_name: str) -> Dict:
        """
        Sử dụng LLM để tạo annotations cho văn bản tiểu sử
        
        Returns:
            Dict với keys: entities, relations
        """
        prompt = f"""
Bạn là chuyên gia NER (Named Entity Recognition) cho văn bản chính trị Việt Nam.

**Nhiệm vụ**: Trích xuất CHÍNH XÁC các entity và quan hệ từ văn bản tiểu sử sau:

**Chính trị gia**: {politician_name}

**Văn bản**:
{summary}

**YÊU CẦU**:

1. **Entities**: Tìm và đánh dấu TẤT CẢ các entity thuộc các loại sau:
   - POSITION: Chức vụ chính trị (VD: "Bí thư Tỉnh ủy Hà Nội", "Thủ tướng Chính phủ")
   - LOCATION: Địa danh (VD: "Hà Nội", "Thành phố Hồ Chí Minh", "Quảng Ninh")
   - ORGANIZATION: Tổ chức, cơ quan (VD: "Bộ Công an", "Quốc hội", "Ban Chấp hành Trung ương Đảng")
   - SCHOOL: Trường học (VD: "Học viện Chính trị Quốc gia Hồ Chí Minh", "Đại học Luật Hà Nội")
   - MILITARY_UNIT: Đơn vị quân đội/công an (VD: "Quân đoàn 1", "Tổng cục An ninh I", "Sư đoàn 312")
   - MILITARY_RANK: Cấp bậc (VD: "Đại tướng", "Trung tướng", "Thượng tướng")
   - AWARD: Huân chương, giải thưởng (VD: "Huân chương Sao vàng", "Anh hùng lao động")
   - CAMPAIGN: Chiến dịch quân sự (VD: "Chiến dịch Điện Biên Phủ", "Chiến tranh biên giới Việt-Trung")
   - ACADEMIC_TITLE: Học hàm, học vị (VD: "Tiến sĩ Luật", "Giáo sư", "Thạc sĩ Kinh tế")
   - PERSON: Tên người khác được nhắc đến (VD: "Nguyễn Phú Trọng", "Phạm Minh Chính")
   - DATE: Thời gian (VD: "2021", "tháng 4 năm 2024", "ngày 10 tháng 12 năm 1958")
   - STATUS: Trạng thái chức vụ (VD: "bị cách chức", "miễn nhiệm", "từ chức")

2. **Vị trí chính xác**: 
   - `start`: Character index bắt đầu của entity trong văn bản (đếm từ 0)
   - `end`: Character index kết thúc của entity (exclusive)
   - `text`: PHẢI là văn bản chính xác từ văn bản gốc (copy nguyên văn)

3. **Relations**: Xác định quan hệ giữa các entity:
   - SERVED_AS: (PERSON → POSITION)
   - BORN_AT, DIED_AT: (PERSON → LOCATION)
   - ALUMNUS_OF: (PERSON → SCHOOL)
   - SERVED_IN: (PERSON → MILITARY_UNIT)
   - HAS_RANK: (PERSON → MILITARY_RANK)
   - AWARDED: (PERSON → AWARD)
   - FOUGHT_IN: (PERSON → CAMPAIGN)
   - HAS_ACADEMIC_TITLE: (PERSON → ACADEMIC_TITLE)
   - SUCCEEDED, PRECEDED: (PERSON → PERSON)

**LƯU Ý**:
- Text của entity PHẢI khớp chính xác với văn bản gốc
- Vị trí start/end PHẢI chính xác (có thể verify bằng summary[start:end] == text)
- Chỉ trích xuất thông tin CÓ TRONG văn bản, KHÔNG bịa đặt
- Với tên chính trị gia chính ({politician_name}), KHÔNG đánh dấu là PERSON entity
"""
        
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.request_interval:
            sleep_time = self.request_interval - time_since_last
            time.sleep(sleep_time)
        
        try:
            response = self.model.generate_content(prompt)
            self.last_request_time = time.time()
            
            result = json.loads(response.text)
            
            # Validate annotations
            entities = result.get("entities", [])
            for ent in entities:
                # Verify position is correct
                extracted = summary[ent["start"]:ent["end"]]
                if extracted != ent["text"]:
                    logger.warning(f"Position mismatch for '{ent['text']}': extracted='{extracted}'")
            
            logger.info(f"Annotated {politician_name}: {len(entities)} entities, {len(result.get('relations', []))} relations")
            return result
            
        except Exception as e:
            error_str = str(e).lower()
            
            if any(err in error_str for err in ["quota", "rate limit", "429", "resource_exhausted"]):
                logger.warning(f"Quota error: {e}")
                
                if self.api_rotator.handle_api_error(e):
                    # Recreate model with new key
                    self.model = genai.GenerativeModel(
                        model_name="gemini-2.5-flash-lite",
                        generation_config={
                            "response_mime_type": "application/json",
                            "response_schema": ANNOTATION_SCHEMA,
                            "temperature": 0.1
                        }
                    )
                    logger.info(f"Retrying with new key: {self.api_rotator.get_current_key_name()}")
                    time.sleep(2)
                    
                    # Retry
                    response = self.model.generate_content(prompt)
                    result = json.loads(response.text)
                    return result
                else:
                    logger.error("All API keys exhausted!")
                    return None
            else:
                logger.error(f"Error annotating {politician_name}: {e}")
                return None
    
    def generate_dataset(self, input_file: str, output_dir: str, 
                        num_samples: int = 300, skip: int = 0):
        """
        Sinh dataset huấn luyện từ dữ liệu politicians
        
        Args:
            input_file: Path to politicians_data_normalized.json
            output_dir: Directory to save training data
            num_samples: Số lượng samples cần sinh
            skip: Bỏ qua bao nhiêu samples đầu tiên
        """
        os.makedirs(output_dir, exist_ok=True)
        
        logger.info(f"Loading data from {input_file}")
        with open(input_file, 'r', encoding='utf-8') as f:
            politicians = json.load(f)
        
        # Filter politicians có summary dài đủ
        valid_politicians = [
            p for p in politicians 
            if p.get("summary") and len(p.get("summary", "")) >= 100
        ]
        
        logger.info(f"Found {len(valid_politicians)} politicians with valid summaries")
        
        # Select samples
        selected = valid_politicians[skip:skip+num_samples]
        
        logger.info(f"Generating annotations for {len(selected)} samples...")
        
        training_data = []
        errors = 0
        
        for politician in tqdm(selected, desc="Annotating"):
            pol_id = f"pol{politician['id']}"
            pol_name = politician["title"]
            summary = politician["summary"]
            
            annotations = self.annotate_text(summary, pol_name)
            
            if annotations:
                training_data.append({
                    "id": pol_id,
                    "name": pol_name,
                    "text": summary,
                    "entities": annotations.get("entities", []),
                    "relations": annotations.get("relations", [])
                })
            else:
                errors += 1
        
        # Save to JSONL format (one JSON per line - standard for NER datasets)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(output_dir, f"training_data_{timestamp}.jsonl")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for sample in training_data:
                f.write(json.dumps(sample, ensure_ascii=False) + '\n')
        
        logger.info(f"Generated {len(training_data)} training samples")
        logger.info(f"Errors: {errors}")
        logger.info(f"Saved to: {output_file}")
        
        # Statistics
        stats = {
            "total_samples": len(training_data),
            "errors": errors,
            "entity_type_counts": {},
            "relation_type_counts": {},
            "avg_entities_per_sample": 0,
            "avg_relations_per_sample": 0
        }
        
        total_entities = 0
        total_relations = 0
        
        for sample in training_data:
            total_entities += len(sample["entities"])
            total_relations += len(sample["relations"])
            
            for ent in sample["entities"]:
                label = ent["label"]
                stats["entity_type_counts"][label] = stats["entity_type_counts"].get(label, 0) + 1
            
            for rel in sample["relations"]:
                rel_type = rel["relation"]
                stats["relation_type_counts"][rel_type] = stats["relation_type_counts"].get(rel_type, 0) + 1
        
        if training_data:
            stats["avg_entities_per_sample"] = total_entities / len(training_data)
            stats["avg_relations_per_sample"] = total_relations / len(training_data)
        
        # Save statistics
        stats_file = os.path.join(output_dir, f"dataset_stats_{timestamp}.json")
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Statistics saved to: {stats_file}")
        print(f"\n{'='*60}")
        print(f"DATASET GENERATION COMPLETE")
        print(f"{'='*60}")
        print(f"Total samples: {len(training_data)}")
        print(f"Avg entities/sample: {stats['avg_entities_per_sample']:.2f}")
        print(f"Avg relations/sample: {stats['avg_relations_per_sample']:.2f}")
        print(f"Output: {output_file}")
        print(f"{'='*60}")
        
        return output_file, stats


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate training data for PhoBERT fine-tuning")
    parser.add_argument(
        "--input", "-i",
        type=str,
        default="data/processed/expand/politicians_data_normalized.json",
        help="Input politicians data file"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="ml/data/training",
        help="Output directory for training data"
    )
    parser.add_argument(
        "--num-samples", "-n",
        type=int,
        default=300,
        help="Number of samples to generate"
    )
    parser.add_argument(
        "--skip", "-s",
        type=int,
        default=0,
        help="Skip first N samples"
    )
    
    args = parser.parse_args()
    
    generator = TrainingDataGenerator()
    generator.generate_dataset(
        input_file=args.input,
        output_dir=args.output,
        num_samples=args.num_samples,
        skip=args.skip
    )

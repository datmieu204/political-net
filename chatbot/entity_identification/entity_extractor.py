import json
import csv
import sys
import os
from typing import Dict, List, Any

qa_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Q_and_A')
sys.path.insert(0, qa_dir)

# Add project root to path for utils import
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Import with no auto-rotation
import google.generativeai as genai
from utils.api_key_rotator import APIKeyRotator

class FixedKeyGeminiClient:
    """Gemini client with fixed key (no auto-rotation)"""
    def __init__(self, key_value: str, model: str = "gemini-2.5-flash-lite"):
        self.model_name = model
        genai.configure(api_key=key_value)
        self.model = genai.GenerativeModel(model)
    
    def generate(self, prompt: str, temperature: float = 0.7, max_tokens: int = 2000) -> str:
        generation_config = genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens
        )
        response = self.model.generate_content(prompt, generation_config=generation_config)
        if response.text:
            content = response.text.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            return content.strip()
        raise Exception("Empty response from Gemini")

ENTITY_EXTRACTION_PROMPT = """Bạn là một AI chuyên trích xuất thông tin từ các câu hỏi chính trị Việt Nam.

## Các loại thực thể (Entity Types) - 12 LOẠI:
- **Politician**: Tên chính trị gia (VD: "Nông Đức Mạnh", "Võ Văn Thưởng")
- **Position**: Chức vụ (VD: "Tổng Bí thư", "Chủ tịch nước")
- **Location**: Địa điểm (VD: "Hà Nội", "Thành phố Hồ Chí Minh")
- **Award**: Giải thưởng (VD: "Huân chương Sao Vàng")
- **MilitaryCareer**: Sự nghiệp quân sự
- **MilitaryRank**: Quân hàm (VD: "Đại tướng", "Thượng tướng")
- **AcademicTitle**: Học vị (VD: "Tiến sĩ Triết học", "Thạc sĩ Luật")
- **AlmaMater**: Trường học (VD: "Đại học Bách Khoa Hà Nội")
- **Campaigns**: Chiến dịch (VD: "Chiến dịch Điện Biên Phủ")
- **BirthDate**: Ngày sinh (VD: "1973", "1966-08-15")
- **DeathDate**: Ngày mất (VD: "2020", "2022-11-30")
- **TermPeriod**: Nhiệm kỳ (VD: "từ 2015 đến 2019", "2020-01-01 đến 2025-12-31")

## Các loại quan hệ (Relation Types) - CHỈ 11 LOẠI SAU, KHÔNG ĐƯỢC TỰ TẠO THÊM:
- **PRECEDED**: Tiền nhiệm
- **SUCCEEDED**: Kế nhiệm
- **BORN_AT**: Nơi sinh
- **DIED_AT**: Nơi mất
- **SERVED_AS**: Đảm nhiệm chức vụ
- **ALUMNUS_OF**: Là cựu sinh viên của
- **HAS_RANK**: Có quân hàm
- **HAS_ACADEMIC_TITLE**: Có học vị
- **AWARDED**: Được trao tặng
- **SERVED_IN**: Phục vụ trong
- **FOUGHT_IN**: Tham gia chiến dịch

**CẢNH BÁO**: 
- KHÔNG được tự tạo relation types mới như "TERM_DURATION", "HAS_BIRTH_DATE", "HAS_DEATH_DATE", etc.
- KHÔNG được dùng entity type (BirthDate, DeathDate, TermPeriod) làm relation type
- CHỈ dùng ĐÚNG 11 relation types ở trên

## Định dạng đầu ra yêu cầu:
```json
{{
  "entities": [
    {{
      "text": "Tên thực thể",
      "type": "Politician | Position | Location | Award | MilitaryCareer | MilitaryRank | AcademicTitle | AlmaMater | Campaigns | BirthDate | DeathDate | TermPeriod"
    }}
  ],
  "relations": [
    {{
      "subject": "Thực thể chủ thể",
      "relation": "PRECEDED | SUCCEEDED | BORN_AT | DIED_AT | SERVED_AS | ALUMNUS_OF | HAS_RANK | HAS_ACADEMIC_TITLE | AWARDED | SERVED_IN | FOUGHT_IN",
      "object": "Thực thể đối tượng"
    }}
  ],
  "intent": {{
    "type": "PRECEDED hoặc SUCCEEDED hoặc BORN_AT hoặc DIED_AT... hoặc UNKNOWN nếu không chắc"
  }}
}}
```

Bây giờ hãy phân tích câu hỏi sau:
{question_data}

CHÚ Ý QUAN TRỌNG: 
- CHỈ sử dụng ĐÚNG 11 relation types đã liệt kê
- KHÔNG tự tạo relation mới
- Chỉ trả về JSON hợp lệ, KHÔNG thêm markdown formatting"""


class EntityExtractor:
    def __init__(self, llm_clients: List):
        self.llm_clients = llm_clients
        self.current_key_idx = 0
        self.last_request_time = {}
        self.key_cooldown = {}
        # Note: previously tracked "dead" keys; removed persistent alive/dead logic
        self.success_count = 0
        self.total_questions = 0
    
    def _get_last_processed_id(self, output_file: str) -> int:
        """Đọc ID cuối cùng đã xử lý từ file JSON"""
        if not os.path.exists(output_file):
            return 0
        
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data and len(data) > 0:
                    last_id = data[-1].get('id', 0)
                    print(f"Found last processed ID: {last_id}")
                    return last_id
        except json.JSONDecodeError:
            print(f"Warning: Could not parse {output_file}, starting from beginning")
            return 0
        except Exception as e:
            print(f"Warning: Error reading {output_file}: {e}")
            return 0
        
        return 0
    
    def _get_next_available_key(self):
        """Rotate to the next key (simple circular rotation)."""
        next_idx = (self.current_key_idx + 1) % len(self.llm_clients)
        self.current_key_idx = next_idx
        return next_idx
    
    def _is_quota_exceeded(self, error_msg: str) -> bool:
        """Kiểm tra xem có phải lỗi quota exceeded (permanent) không"""
        error_lower = error_msg.lower()
        return (
            'exceeded your current quota' in error_lower or
            'quota exceeded' in error_lower or
            'billing' in error_lower
        )
    
    def _is_rate_limit(self, error_msg: str) -> bool:
        """Kiểm tra xem có phải rate limit (temporary) không"""
        error_lower = error_msg.lower()
        return (
            'resource_exhausted' in error_lower or
            ('429' in error_lower and 'quota' not in error_lower)
        )
    
    def _process_single_question(self, args):
        import time
        idx, row, question_type = args

        max_retries = len(self.llm_clients)
        retry_count = 0
        tried_keys = set()

        while retry_count < max_retries:
            client_idx = self.current_key_idx
            client = self.llm_clients[client_idx]

            # Kiểm tra cooldown
            if client_idx in self.key_cooldown:
                wait_time = self.key_cooldown[client_idx] - time.time()
                if wait_time > 0:
                    print(f"[{idx}] Key {client_idx} in cooldown, waiting {wait_time:.1f}s...")
                    time.sleep(wait_time)
                del self.key_cooldown[client_idx]

            # Delay tối thiểu 1s giữa các requests (tăng để tránh rate limit)
            if client_idx in self.last_request_time:
                elapsed = time.time() - self.last_request_time[client_idx]
                if elapsed < 1.0:
                    wait_time = 1.0 - elapsed
                    time.sleep(wait_time)

            self.last_request_time[client_idx] = time.time()

            try:
                question_data = {
                    "question": row['question'],
                    "question_type": question_type,
                    "hop_count": int(row['hop_count']) if row['hop_count'] else None,
                    "reasoning_path": row['reasoning_path']
                }

                prompt = ENTITY_EXTRACTION_PROMPT.format(
                    question_data=json.dumps(question_data, ensure_ascii=False, indent=2)
                )
                response = client.generate(prompt)

                try:
                    extraction = json.loads(response)
                except json.JSONDecodeError:
                    extraction = {
                        "entities": [],
                        "relations": [],
                        "intent": {},
                        "error": "Failed to parse LLM response",
                        "raw_response": response
                    }

                # Extract unique relation types
                relations = extraction.get('relations', [])
                unique_relations = []
                seen_relations = set()

                for rel in relations:
                    relation_type = rel.get('relation', '')
                    if relation_type and relation_type not in seen_relations:
                        unique_relations.append(relation_type)
                        seen_relations.add(relation_type)

                result = {
                    'id': int(row['id']),
                    'question': row['question'],
                    'answer_json': {
                        'entities': extraction.get('entities', []),
                        'intent_relation': unique_relations
                    }
                }

                self.success_count += 1
                print(f"[{idx}] {question_type.upper()} ID:{row['id']} | Key:{client_idx} | Progress: {self.success_count}/{self.total_questions}")
                return result

            except Exception as e:
                error_msg = str(e)

                # Kiểm tra loại lỗi
                if self._is_quota_exceeded(error_msg):
                    # Quota exceeded - rotate to next key
                    print(f"[{idx}] Key {client_idx} DEAD (quota exceeded)")
                    tried_keys.add(client_idx)
                    # Rotate to next key
                    self._get_next_available_key()
                    time.sleep(5)

                    # Nếu tất cả keys đều đã thử và đều báo quota exceeded, quay lại key 1
                    if len(tried_keys) >= len(self.llm_clients):
                        print(f"[{idx}] All keys reported quota exceeded; resetting to key 1 and retrying...")
                        self.current_key_idx = 0
                        tried_keys.clear()
                        time.sleep(5)

                    retry_count += 1
                    continue

                elif self._is_rate_limit(error_msg):
                    # Rate limit tạm thời - đặt cooldown và chuyển key
                    print(f"[{idx}] Key {client_idx} rate limited (temporary)")
                    self.key_cooldown[client_idx] = time.time() + 180  # 3 phút cooldown
                    self._get_next_available_key()
                    print(f"[{idx}] Switching to key {self.current_key_idx}, waiting 5s before next request...")
                    time.sleep(5)
                    retry_count += 1
                    continue

                else:
                    # Lỗi khác
                    print(f"[{idx}] Unexpected error with key {client_idx}: {error_msg[:150]}")
                    return {
                        'id': int(row['id']),
                        'question': row['question'],
                        'answer_json': {
                            'entities': [],
                            'intent_relation': [],
                            'error': error_msg[:200]
                        }
                    }

        # Hết retries
        return {
            'id': int(row['id']),
            'question': row['question'],
            'answer_json': {
                'entities': [],
                'intent_relation': [],
                'error': 'Max retries exceeded'
            }
        }
    
    def process_dataset(self, input_file: str, output_file: str, question_type: str, 
                       limit: int = None, workers: int = 1, target_total: int = None):
        """
        Process dataset và ghi tiếp vào file JSON
        
        Args:
            target_total: Tổng số câu hỏi mục tiêu (ví dụ: 1500 cho MCQ)
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        
        # Đọc ID cuối cùng đã xử lý
        last_processed_id = self._get_last_processed_id(output_file)
        
        # Đọc số câu hỏi hiện có
        current_count = 0
        if os.path.exists(output_file):
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    current_count = len(data)
            except:
                current_count = 0
        
        # Nếu có target_total, tính số câu còn thiếu
        if target_total and current_count >= target_total:
            print(f"Already have {current_count}/{target_total} questions. No need to process more!")
            return []
        
        remaining_needed = target_total - current_count if target_total else None
        
        # Đọc questions từ CSV
        with open(input_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            all_questions = list(reader)
        
        # Lọc các câu hỏi chưa xử lý
        questions = [q for q in all_questions if int(q['id']) > last_processed_id]
        
        # Giới hạn số câu cần chạy nếu có target_total
        if remaining_needed:
            questions = questions[:remaining_needed]
            print(f"Target: {target_total} total questions")
            print(f"   Current: {current_count} questions")
            print(f"   Need: {remaining_needed} more questions")
        
        if limit and not target_total:
            questions = questions[:limit]
        
        if not questions:
            print(f"All questions processed or target reached!")
            return []
        
        self.total_questions += len(questions)
        print(f"Processing {len(questions)} {question_type.upper()} questions (starting from ID {questions[0]['id']})...")
        print(f"   Total in CSV: {len(all_questions)} | Already processed: {last_processed_id}")
        
        # Chuẩn bị tasks
        tasks = []
        for idx, row in enumerate(questions):
            tasks.append((idx + 1, row, question_type))
        
        results = []
        write_lock = threading.Lock()
        
        # Kiểm tra xem file đã có dữ liệu chưa
        file_exists = os.path.exists(output_file)
        has_data = False
        
        if file_exists:
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                    has_data = len(existing_data) > 0
            except:
                has_data = False
        
        # Nếu file chưa tồn tại hoặc rỗng, tạo mới với array
        if not file_exists or not has_data:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write('[\n')
        else:
            # File đã có dữ liệu, xóa dấu ] cuối để ghi tiếp
            with open(output_file, 'r+', encoding='utf-8') as f:
                f.seek(0, 2)  # Đi đến cuối file
                file_size = f.tell()
                
                # Tìm vị trí của ] cuối cùng
                f.seek(max(0, file_size - 100))
                content = f.read()
                
                # Xóa ] và khoảng trắng cuối
                pos = content.rfind(']')
                if pos != -1:
                    f.seek(file_size - (len(content) - pos))
                    f.truncate()
                    f.write(',\n')  # Thêm dấu phẩy để nối tiếp
        
        # Process questions
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(self._process_single_question, task): task for task in tasks}
            
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                
                # Ghi ngay vào file
                with write_lock:
                    with open(output_file, 'a', encoding='utf-8') as f:
                        json_str = json.dumps(result, ensure_ascii=False, indent=2)
                        f.write(json_str)
                        f.write(',\n')
                
                # Kiểm tra nếu đã đủ số lượng mục tiêu
                if target_total and (current_count + len(results)) >= target_total:
                    print(f"Reached target of {target_total} questions! Stopping...")
                    # Cancel remaining futures
                    for f in futures:
                        f.cancel()
                    break
        
        # Xóa dấu phẩy cuối và đóng array
        with open(output_file, 'r+', encoding='utf-8') as f:
            f.seek(0, 2)
            f.seek(f.tell() - 2)  # Quay lại trước dấu phẩy cuối
            f.truncate()
            f.write('\n]')
        
        final_count = current_count + len(results)
        print(f"Saved {len(results)} {question_type.upper()} extractions to {output_file}")
        print(f"Total questions in file: {final_count}/{target_total if target_total else '∞'}")
        
        return results
    
    def process_both_datasets(self, mcq_file: str, tf_file: str, 
                            output_dir: str, mcq_target: int = 1500, 
                            tf_target: int = 1500, workers: int = 1):
        """
        Process both datasets with target totals.
        
        Args:
            mcq_target: Target total for MCQ questions (default: 1500)
            tf_target: Target total for True/False questions (default: 1500)
        """
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        mcq_output = os.path.join(output_dir, 'mcq_entity_extraction.json')
        tf_output = os.path.join(output_dir, 'tf_entity_extraction.json')
        
        print("Processing MCQ Questions...")
        mcq_results = self.process_dataset(
            mcq_file, mcq_output, 'mcq', 
            workers=workers, target_total=mcq_target
        )
        
        print("Processing True/False Questions...")
        tf_results = self.process_dataset(
            tf_file, tf_output, 'true_false', 
            workers=workers, target_total=tf_target
        )
        
        print("SUMMARY")
        print(f"MCQ Questions Processed (this run): {len(mcq_results)}")
        print(f"True/False Questions Processed (this run): {len(tf_results)}")
        print(f"Total (this run): {len(mcq_results) + len(tf_results)}")
        print(f"\nOutput files:")
        print(f"  - {mcq_output}")
        print(f"  - {tf_output}")
        
        return {'mcq': mcq_results, 'true_false': tf_results}


def main():
    import time
    
    # Initialize key rotator and get ALL keys
    key_rotator = APIKeyRotator()
    
    # Use a subset of keys for testing
    num_keys_to_use = 10  # Use first 15 keys
    num_keys = min(num_keys_to_use, len(key_rotator.keys))
    llm_clients = []
    
    print(f"Initializing {num_keys} API clients (out of {len(key_rotator.keys)} available)...")
    for idx in range(num_keys):
        key_name, key_value = key_rotator.keys[idx]
        client = FixedKeyGeminiClient(key_value)
        llm_clients.append(client)
        if (idx + 1) % 10 == 0 or idx == num_keys - 1:
            print(f"Initialized {idx+1}/{num_keys} clients")
    
    extractor = EntityExtractor(llm_clients)
    
    mcq_file = '../Q_and_A/output/mcq_questions.csv'
    tf_file = '../Q_and_A/output/true_false_questions.csv'
    output_dir = 'output'
    
    # Targets
    mcq_target = 1500  # Target 1500 MCQ
    tf_target = 1500   # Target 1500 True/False
    
    num_workers = 1  # Sequential processing
    
    print("ENTITY EXTRACTION CONFIGURATION")
    print(f"Mode: RESUME - Continue from last processed ID")
    print(f"MCQ Target: {mcq_target} questions")
    print(f"True/False Target: {tf_target} questions")
    print(f"Total API Keys: {num_keys} (out of {len(key_rotator.keys)} available)")
    print(f"Workers: {num_workers}")
    print(f"Strategy: Smart key management with conservative rate limiting")
    print(f"  - Auto-detect quota exceeded (permanent) vs rate limit (temporary)")
    # Note: removed permanent alive/dead key bookkeeping; keys are rotated circularly
    print(f"  - Rate-limited keys get 180s (3 min) cooldown")
    print(f"  - Min delay: 1s between requests (conservative)")
    print(f"  - Delay 5s after switching keys to avoid immediate rate limit")
    print(f"Output directory: {output_dir}")
    
    start_time = time.time()
    
    results = extractor.process_both_datasets(
        mcq_file=mcq_file,
        tf_file=tf_file,
        output_dir=output_dir,
        mcq_target=mcq_target,
        tf_target=tf_target,
        workers=num_workers
    )
    
    elapsed_time = time.time() - start_time
    
    total_processed = len(results['mcq']) + len(results['true_false'])
    
    print("EXTRACTION COMPLETED")
    print(f"Total time: {elapsed_time / 60:.2f} minutes ({elapsed_time:.2f} seconds)")
    if total_processed > 0:
        print(f"Average time per question: {elapsed_time / total_processed:.2f} seconds")
    print(f"Total API keys: {num_keys}")


if __name__ == '__main__':
    main()
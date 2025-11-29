"""
LLM client for generating question variants using Google Gemini.
"""

import os
import json
import time
import logging
from typing import Optional, List, Dict
import google.generativeai as genai

# Import existing key rotator
import sys
# Add project root to path (go up 2 levels: Q_and_A -> chatbot -> project_root)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from utils.api_key_rotator import APIKeyRotator

logger = logging.getLogger(__name__)


class GeminiClient:
    """Google Gemini API client with retry logic and automatic key rotation."""
    
    def __init__(self, model: str = "gemini-2.5-flash-lite", max_retries: int = 3):
        """
        Initialize Gemini client.
        
        Args:
            model: Model name (default: "gemini-1.5-flash")
            max_retries: Maximum number of retries on failure
        """
        self.model = model
        self.max_retries = max_retries
        
        # Initialize key rotator (uses existing utils/api_key_rotator.py)
        try:
            self.key_rotator = APIKeyRotator()
            logger.info(f"Using {self.key_rotator.get_current_key_name()} with {len(self.key_rotator.keys)} keys available")
        except Exception as e:
            raise ValueError(f"Failed to initialize API key rotator: {e}")
        
        # Initialize Gemini model
        self.model_instance = genai.GenerativeModel(model)
        logger.info(f"Gemini client initialized with model: {model}")



    
    def generate(self, prompt: str, temperature: float = 0.7, 
                 max_tokens: int = 2000) -> str:
        """
        Generate text using Gemini API with exponential backoff and key rotation.
        
        Args:
            prompt: Input prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
        
        Returns:
            Generated JSON text
        """
        return self._generate_with_gemini(prompt, temperature, max_tokens)
    
    def _generate_with_gemini(self, prompt: str, temperature: float, 
                             max_tokens: int) -> str:
        """Generate using Google Gemini API with key rotation."""
        for attempt in range(self.max_retries):
            try:
                # Configure generation parameters
                generation_config = genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens
                )
                
                # Generate response with JSON mode hint in prompt
                full_prompt = f"{prompt}\n\nIMPORTANT: Return ONLY valid JSON, no markdown formatting."
                response = self.model_instance.generate_content(
                    full_prompt,
                    generation_config=generation_config
                )
                
                # Extract text from response
                if response.text:
                    content = response.text.strip()
                    # Clean markdown code blocks if present
                    if content.startswith("```json"):
                        content = content[7:]
                    if content.startswith("```"):
                        content = content[3:]
                    if content.endswith("```"):
                        content = content[:-3]
                    content = content.strip()
                    
                    logger.debug(f"Gemini response (attempt {attempt + 1}): {content[:200]}...")
                    return content
                else:
                    logger.warning(f"Empty response from Gemini")
                    raise Exception("Empty response from Gemini")
                
            except Exception as e:
                logger.warning(f"Gemini generation failed (attempt {attempt + 1}/{self.max_retries}): {e}")
                
                # Try key rotation if it's a quota/rate limit error
                if self.key_rotator.handle_api_error(e):
                    logger.info(f"Retrying with {self.key_rotator.get_current_key_name()}...")
                    # Reinitialize model with new key
                    self.model_instance = genai.GenerativeModel(self.model)
                    time.sleep(1)  # Brief pause before retry
                    continue
                
                # Standard retry logic for other errors
                if attempt < self.max_retries - 1:
                    wait_time = (2 ** attempt)  # Exponential backoff: 1, 2, 4 seconds
                    logger.info(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    raise
        
        raise Exception(f"Failed to generate after {self.max_retries} attempts")
    


def create_llm_client(model: str = "gemini-2.5-flash-lite", **kwargs) -> GeminiClient:
    """
    Create Gemini LLM client.
    
    Args:
        model: Model name (default: "gemini-2.5-flash-lite")
        **kwargs: Additional arguments (max_retries, etc.)
    
    Returns:
        GeminiClient instance
    """
    return GeminiClient(model=model, **kwargs)


# LLM Prompt Template
VARIANT_GENERATION_PROMPT = """Bạn là một trợ lý tạo dữ liệu cho benchmark suy luận multi-hop trên knowledge graph (KG). Mục tiêu: tạo các câu hỏi UNANSWERABLE / PARAPHRASE_HARD dựa trên seed facts.

**NHIỆM VỤ:**
Cho một câu hỏi gốc (seed question) đã có đáp án đúng từ KG, hãy sinh ra 2 biến thể:

1. **UNANSWERABLE**: Câu hỏi tương tự nhưng KHÔNG THỂ TRẢ LỜI được từ KG (thiếu thông tin, hoặc hỏi về thực thể/quan hệ không tồn tại).
2. **PARAPHRASE_HARD**: Diễn đạt lại câu hỏi gốc một cách PHỨC TẠP, khó hiểu hơn (dùng ngữ cảnh gián tiếp, đảo ngữ, hoặc thêm mệnh đề phụ) nhưng VẪN CÓ ĐÁP ÁN ĐÚNG như câu gốc.

**SEED QUESTION:**
{seed_question}

**THÔNG TIN BỐI CẢNH (từ KG):**
- Loại câu hỏi: {q_type}
- Số bước suy luận (hop_count): {hop_count}
- Đường đi suy luận (reasoning_path): {reasoning_path}
- Đáp án: {answer}

**YÊU CẦU OUTPUT:**
Trả về JSON object với cấu trúc sau (KHÔNG thêm text nào khác ngoài JSON):

```json
{{
  "variants": [
    {{
      "variant_type": "UNANSWERABLE",
      "question": "<câu hỏi không thể trả lời>",
      "reasoning_hint": "<giải thích ngắn gọn tại sao không thể trả lời>"
    }},
    {{
      "variant_type": "PARAPHRASE_HARD",
      "question": "<câu hỏi diễn đạt phức tạp>",
      "reasoning_hint": "<giải thích cách diễn đạt khác>"
    }}
  ]
}}
```

**LƯU Ý:**
- Giữ nguyên ngôn ngữ tiếng Việt
- UNANSWERABLE: Đảm bảo thực sự không có đáp án trong KG (vd: hỏi về người khác, địa điểm khác, thời gian khác)
- PARAPHRASE_HARD: Giữ nguyên ý nghĩa nhưng diễn đạt phức tạp hơn nhiều
- Chỉ trả về JSON, không thêm giải thích
"""


def format_variant_prompt(seed_question: str, q_type: str, hop_count: int,
                              reasoning_path: List[str], answer: str) -> str:
    """
    Format the variant generation prompt with seed data.
    
    Args:
        seed_question: Original question text
        q_type: Question type (TRUE_FALSE, YES_NO, MCQ)
        hop_count: Number of reasoning hops
        reasoning_path: List of alternating nodes and relations
        answer: Ground truth answer
    
    Returns:
        Formatted prompt string
    """
    # Format reasoning path for readability
    path_str = " -> ".join(reasoning_path)
    
    return VARIANT_GENERATION_PROMPT.format(
        seed_question=seed_question,
        q_type=q_type,
        hop_count=hop_count,
        reasoning_path=path_str,
        answer=answer
    )


def parse_llm_response(response: str, max_attempts: int = 2) -> Optional[Dict]:
    """
    Parse LLM JSON response with fallback extraction.
    
    Args:
        response: Raw LLM response text
        max_attempts: Number of parsing attempts
    
    Returns:
        Parsed JSON dict or None if failed
    """
    # Attempt 1: Direct JSON parse
    try:
        data = json.loads(response)
        if "variants" in data:
            return data
    except json.JSONDecodeError:
        pass
    
    # Attempt 2: Extract JSON from markdown code block
    try:
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            json_str = response[start:end].strip()
            data = json.loads(json_str)
            if "variants" in data:
                return data
    except (json.JSONDecodeError, ValueError):
        pass
    
    # Attempt 3: Find any JSON object in response
    try:
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            json_str = response[start:end]
            data = json.loads(json_str)
            if "variants" in data:
                return data
    except (json.JSONDecodeError, ValueError):
        pass
    
    logger.error(f"Failed to parse LLM response after {max_attempts} attempts")
    logger.debug(f"Raw response: {response[:500]}...")
    return None

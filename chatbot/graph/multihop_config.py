# chatbot/graph/multihop_config.py

# Maximum số hops cho mỗi pattern
PATTERN_MAX_HOPS = {
    "simple": 1,
    "chain": 3,
    "path": 4,
    "comparison": 2,
    "aggregation": 2,
    "explore": 4
}

# Keywords để detect patterns (fallback, không phải primary method)
PATTERN_KEYWORDS = {
    "path": [
        r"mối quan hệ",
        r"liên quan",
        r"kết nối",
        r"từ.*đến",
        r"giữa.*và",
        r"có.*quan.*hệ",
        r"có.*liên.*kết"
    ],
    "chain": [
        r"tiền nhiệm",
        r"kế nhiệm", 
        r"trước.*sau",
        r"thay thế",
        r"người kế",
        r"người trước",
        r"sau.*ai",
        r"trước.*ai"
    ],
    "comparison": [
        r"so sánh",
        r"nhiều hơn",
        r"ít hơn",
        r"cao hơn",
        r"thấp hơn",
        r"già hơn",
        r"trẻ hơn",
        r"giống",
        r"khác",
        r"ai.*nhiều",
        r"ai.*ít"
    ],
    "aggregation": [
        r"tất cả",
        r"danh sách",
        r"có bao nhiêu",
        r"đếm",
        r"tổng số",
        r"mấy người",
        r"những ai"
    ]
}

# Pattern detection strategies (multi-level)
PATTERN_DETECTION_STRATEGIES = {
    "entity_count": {
        # Số lượng entities ảnh hưởng đến pattern
        "single": "simple",      # 1 entity -> simple
        "two_plus": "explore",   # 2+ entities -> có thể explore/comparison
    },
    "intent_relation_mapping": {
        # Intent relation -> pattern hint
        "PRECEDED": "chain",
        "SUCCEEDED": "chain",
        "BORN_AT": "simple",
        "DIED_AT": "simple",
        "SERVED_AS": "simple",
        "ALUMNUS_OF": "simple",
        "AWARDED": "simple",
        # Multiple intents -> explore
    },
    "question_structure": {
        # Cấu trúc câu hỏi
        "contains_and": "explore",        # "A và B" -> explore nhiều facts
        "contains_or": "comparison",      # "A hay B" -> comparison
        "multiple_clauses": "explore",    # Nhiều mệnh đề -> explore
        "single_clause": "simple",        # Một mệnh đề -> simple
    },
    "semantic_patterns": {
        # Patterns ngữ nghĩa
        "verification": "explore",        # "...đúng không?" -> verify facts
        "multiple_choice": "explore",     # "A, B, C, D?" -> explore options
        "true_false": "explore",          # TF questions -> explore
        "relationship_query": "path",     # Hỏi về mối quan hệ -> path
        "succession": "chain",            # Tiền/kế nhiệm -> chain
    }
}

# Scoring weights cho pattern detection
PATTERN_DETECTION_WEIGHTS = {
    "keyword_match": 0.3,        # Keywords chỉ chiếm 30%
    "entity_count": 0.2,         # Entity count 20%
    "intent_relation": 0.3,      # Intent relation 30%
    "question_structure": 0.2,   # Question structure 20%
}

# Default pattern nếu không detect được
DEFAULT_PATTERN = "explore"  # Explore là pattern an toàn nhất

# Pattern priority (nếu có conflict)
PATTERN_PRIORITY = [
    "chain",        # Ưu tiên cao nhất (cụ thể)
    "comparison",   # Ưu tiên cao
    "path",         # Ưu tiên trung bình
    "aggregation",  # Ưu tiên thấp
    "simple",       # Ưu tiên thấp
    "explore"       # Default/fallback
]

# Default query limits
QUERY_LIMITS = {
    "hop_1": 20,
    "hop_2": 15,
    "hop_3": 10,
    "hop_4": 5
}

# Relations có thể skip trong exploration (quá phổ biến hoặc ít giá trị)
SKIP_RELATIONS_IN_EXPLORATION = [
    "BORN_AT",
    "DIED_AT",
]

# Prioritized relations cho từng pattern
PATTERN_RELATIONS = {
    "chain": ["PRECEDED", "SUCCEEDED", "SERVED_AS"],
    "path": ["BORN_AT", "ALUMNUS_OF", "SERVED_AS", "AWARDED", "PRECEDED", "SUCCEEDED"],
    "comparison": ["AWARDED", "SERVED_AS", "ALUMNUS_OF"],
    "aggregation": ["AWARDED", "FOUGHT_IN", "SERVED_IN"]
}

# LLM prompts templates
DECISION_PROMPT_TEMPLATE = """
Câu hỏi: "{question}"

Thông tin đã thu thập qua {hop_count} bước suy luận:
{accumulated_context}

Đánh giá: Đã có đủ thông tin để trả lời chính xác câu hỏi chưa?

QUY TẮC:
- Nếu đã có đủ thông tin cụ thể để trả lời -> Trả lời "ĐỦ"
- Nếu còn thiếu thông tin quan trọng -> Trả lời "CHƯA ĐỦ"
- Nếu đã đạt {max_hops} bước mà chưa đủ -> Cố gắng trả lời với thông tin hiện có

TRẢ LỜI CHỈ MỘT TRONG HAI: "ĐỦ" hoặc "CHƯA ĐỦ"
"""

HOP_SUMMARY_TEMPLATE = """
Kết quả từ bước suy luận {hop_number}:

Dữ liệu (top 5 records):
{subgraph_sample}

Nhiệm vụ: Tóm tắt ngắn gọn (1-2 câu) những thông tin quan trọng từ kết quả này.
Tập trung vào:
- Entities mới phát hiện
- Relationships quan trọng
- Thuộc tính đáng chú ý

Tóm tắt:
"""

FINAL_SUMMARY_TEMPLATE = """
Câu hỏi: "{question}"

Quy trình suy luận qua {total_hops} bước:
{reasoning_steps}

Thông tin tổng hợp:
{accumulated_context}

Nhiệm vụ: 
1. Tổng hợp lại toàn bộ thông tin đã tìm được
2. Làm rõ mối quan hệ giữa các thực thể
3. Sắp xếp theo logic dễ hiểu
4. Viết bằng tiếng Việt, rõ ràng và có cấu trúc

Tóm tắt:
"""

# Entity extraction patterns
ENTITY_EXTRACTION_PATTERNS = {
    "name_fields": ["name", "politician", "source_entity", "node_0", "node_1"],
    "min_entity_length": 3,
    "max_entities_to_keep": 10
}

# Graph traversal configurations
GRAPH_TRAVERSAL_CONFIG = {
    "max_path_length": 4,
    "explore_node_types": [
        "Politician", 
        "Position", 
        "Location", 
        "AlmaMater", 
        "Award",
        "MilitaryRank"
    ],
    "bidirectional_relations": ["PRECEDED", "SUCCEEDED"]
}

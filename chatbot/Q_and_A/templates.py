"""
Question templates for generating Vietnamese multi-hop reasoning questions.
"""

import random
from typing import Dict, List, Tuple, Optional


# Edge type to Vietnamese relation mapping
RELATION_TEMPLATES = {
    "SERVED_AS": {
        "forward": "đã từng giữ chức vụ",
        "backward": "là chức vụ được giữ bởi",
        "question": "giữ chức vụ gì",
        "variants": ["đảm nhiệm vị trí", "làm việc với cương vị", "được bổ nhiệm làm"]
    },
    "SUCCEEDED": {
        "forward": "kế nhiệm",
        "backward": "được kế nhiệm bởi",
        "question": "kế nhiệm ai",
        "variants": ["nối nghiệp", "tiếp nối", "thay thế"]
    },
    "PRECEDED": {
        "forward": "tiền nhiệm",
        "backward": "có tiền nhiệm là",
        "question": "là tiền nhiệm của ai",
        "variants": ["đi trước", "có nhiệm kỳ trước"]
    },
    "BORN_AT": {
        "forward": "sinh tại",
        "backward": "là nơi sinh của",
        "question": "sinh ở đâu",
        "variants": ["quê quán tại", "có quê ở", "ra đời tại"]
    },
    "DIED_AT": {
        "forward": "qua đời tại",
        "backward": "là nơi mất của",
        "question": "mất ở đâu",
        "variants": ["từ trần tại", "qua đời ở"]
    },
    "AWARDED": {
        "forward": "được trao tặng",
        "backward": "là giải thưởng của",
        "question": "nhận giải thưởng gì",
        "variants": ["được vinh danh", "được tặng thưởng", "nhận danh hiệu"]
    },
    "SERVED_IN": {
        "forward": "phục vụ trong",
        "backward": "có thành viên",
        "question": "phục vụ trong đơn vị nào",
        "variants": ["công tác tại", "hoạt động trong"]
    },
    "HAS_RANK": {
        "forward": "có cấp bậc",
        "backward": "là cấp bậc của",
        "question": "có cấp bậc gì",
        "variants": ["đạt quân hàm", "được phong hàm"]
    },
    "FOUGHT_IN": {
        "forward": "tham gia chiến dịch",
        "backward": "có sự tham gia của",
        "question": "tham gia chiến dịch nào",
        "variants": ["chiến đấu trong", "tham chiến tại"]
    },
    "ALUMNUS_OF": {
        "forward": "là cựu sinh viên của",
        "backward": "có cựu sinh viên",
        "question": "tốt nghiệp trường nào",
        "variants": ["học tại", "từng học ở", "đào tạo tại"]
    },
    "HAS_ACADEMIC_TITLE": {
        "forward": "có học vị",
        "backward": "là học vị của",
        "question": "có học vị gì",
        "variants": ["đạt bằng", "được phong học hàm"]
    },
    "BORN_YEAR": {
        "forward": "sinh năm",
        "backward": "là năm sinh của",
        "question": "sinh năm bao nhiêu",
        "variants": ["cất tiếng khóc chào đời năm", "ra đời năm"]
    },
    "DIED_YEAR": {
        "forward": "mất năm",
        "backward": "là năm mất của",
        "question": "mất năm bao nhiêu",
        "variants": ["qua đời năm", "từ trần năm"]
    },
    "TERM_DURATION": {
        "forward": "có nhiệm kỳ",
        "backward": "là nhiệm kỳ của",
        "question": "có nhiệm kỳ từ bao nhiêu đến bao nhiêu",
        "variants": ["giữ chức trong khoảng thời gian", "đảm nhiệm trong giai đoạn"]
    }
}


def get_relation_phrase(edge_type: str, direction: str = "forward") -> str:
    """Get Vietnamese phrase for relation."""
    if edge_type in RELATION_TEMPLATES:
        return RELATION_TEMPLATES[edge_type].get(direction, edge_type)
    return edge_type


def get_relation_variant(edge_type: str) -> str:
    """Get a random variant phrase for relation."""
    if edge_type in RELATION_TEMPLATES and "variants" in RELATION_TEMPLATES[edge_type]:
        return random.choice(RELATION_TEMPLATES[edge_type]["variants"])
    return get_relation_phrase(edge_type)


def format_relation_with_context(edge_type: str, edge_props: Dict, kg, direction: str = "forward") -> str:
    """
    Format relation phrase with contextual information (position, dates, etc).
    
    Args:
        edge_type: Type of edge (PRECEDED, SUCCEEDED, SERVED_AS, etc.)
        edge_props: Edge properties dict (position_id, term_start, term_end, etc.)
        kg: KnowledgeGraph instance to lookup position names
        direction: "forward" or "backward"
    
    Returns:
        Rich relation phrase with context
    """
    base_phrase = get_relation_phrase(edge_type, direction)
    
    # Handle PRECEDED/SUCCEEDED - add position context
    if edge_type in ["PRECEDED", "SUCCEEDED"] and edge_props.get("position_id"):
        position_id = edge_props["position_id"]
        position_node = kg.get_node(position_id)
        if position_node:
            position_name = position_node.get("name", "")
            if position_name:
                if edge_type == "PRECEDED":
                    return f"là tiền nhiệm của ai trong chức vụ {position_name}"
                elif edge_type == "SUCCEEDED":
                    return f"kế nhiệm ai trong chức vụ {position_name}"
    
    # Handle SERVED_AS - add term dates
    elif edge_type == "SERVED_AS" and (edge_props.get("term_start") or edge_props.get("term_end")):
        term_start = edge_props.get("term_start", "")
        term_end = edge_props.get("term_end", "")
        if term_start and term_end:
            if term_end == "nay":
                return f"{base_phrase} (từ {term_start} đến nay)"
            else:
                return f"{base_phrase} (từ {term_start} đến {term_end})"
        elif term_start:
            return f"{base_phrase} (từ {term_start})"
    
    return base_phrase


# Single-hop question templates - CỤ THỂ và DỄ HIỂU
SINGLE_HOP_TEMPLATES = {
    "TRUE_FALSE": [
        "{subject} {relation} {object}. Đúng hay sai?",
        "Phát biểu sau đây đúng hay sai: {subject} {relation} {object}.",
    ],
    "YES_NO": [
        "{subject} có {relation} {object} không?",
        "Có phải {subject} {relation} {object} không?",
    ],
    "MCQ": [
        "{subject} {relation_question}?",
    ]
}


# Multi-hop question templates - RÕ RÀNG và CỤ THỂ
MULTI_HOP_TEMPLATES = {
    "2_HOP": {
        "TRUE_FALSE": [
            "{entity1} {rel1} {entity2}, và {entity2} {rel2} {entity3}. Đúng hay sai?",
        ],
        "MCQ": [
            "{entity1} {rel1_question}, và người/thực thể đó {rel2_question}?",
        ]
    },
    "3_HOP": {
        "TRUE_FALSE": [
            "{entity1} {rel1} {entity2}, {entity2} {rel2} {entity3}, và {entity3} {rel3} {entity4}. Đúng hay sai?",
        ],
        "MCQ": [
            "{entity1} {rel1_question}, người/thực thể đó {rel2_question}, và cuối cùng {rel3_question}?",
        ]
    },
    "4_HOP": {
        "TRUE_FALSE": [
            "{entity1} {rel1} {entity2}, {entity2} {rel2} {entity3}, {entity3} {rel3} {entity4}, và {entity4} {rel4} {entity5}. Đúng hay sai?",
        ],
        "MCQ": [
            "{entity1} {rel1_question}, người/thực thể đó {rel2_question}, tiếp theo {rel3_question}, và cuối cùng {rel4_question}?",
        ]
    }
}


def generate_single_hop_question(subject_name: str, relation: str, object_name: str,
                                 q_type: str, seed: Optional[int] = None) -> str:
    """
    Generate a single-hop question in Vietnamese.
    
    Args:
        subject_name: Subject entity name
        relation: Relation type
        object_name: Object entity name
        q_type: Question type (TRUE_FALSE, YES_NO, MCQ)
        seed: Random seed for template selection
    
    Returns:
        Generated question string
    """
    if seed is not None:
        random.seed(seed)
    
    templates = SINGLE_HOP_TEMPLATES.get(q_type, SINGLE_HOP_TEMPLATES["YES_NO"])
    template = random.choice(templates)
    
    relation_phrase = get_relation_phrase(relation)
    relation_question = RELATION_TEMPLATES.get(relation, {}).get("question", relation_phrase)
    
    question = template.format(
        subject=subject_name,
        relation=relation_phrase,
        object=object_name,
        relation_question=relation_question
    )
    
    return question


def generate_multi_hop_question(path: List[str], node_names: Dict[str, str],
                                q_type: str, hop_count: int,
                                seed: Optional[int] = None) -> str:
    """
    Generate a multi-hop question in Vietnamese.
    
    Args:
        path: Alternating list [node_id, edge_type, node_id, ...]
        node_names: Mapping from node_id to name
        q_type: Question type
        hop_count: Number of hops
        seed: Random seed
    
    Returns:
        Generated question string
    """
    if seed is not None:
        random.seed(seed)
    
    # Extract entities and relations
    entities = []
    relations = []
    for i, item in enumerate(path):
        if i % 2 == 0:  # Node
            name = node_names.get(item, item)
            entities.append(name)
        else:  # Relation
            relations.append(item)
    
    # Select template based on hop count
    hop_key = f"{hop_count}_HOP"
    if hop_key not in MULTI_HOP_TEMPLATES:
        hop_key = "2_HOP"  # Fallback
    
    templates = MULTI_HOP_TEMPLATES[hop_key].get(q_type, 
                                                  MULTI_HOP_TEMPLATES[hop_key].get("YES_NO", []))
    
    if not templates:
        # Fallback to simple template
        rel_phrases = [get_relation_phrase(r) for r in relations]
        return f"{entities[0]} có liên hệ với {entities[-1]} qua chuỗi quan hệ: {' → '.join(rel_phrases)}?"
    
    template = random.choice(templates)
    
    # Prepare template variables
    template_vars = {}
    for i, entity in enumerate(entities, 1):
        template_vars[f"entity{i}"] = entity
    
    for i, relation in enumerate(relations, 1):
        template_vars[f"rel{i}"] = get_relation_phrase(relation)
        template_vars[f"rel{i}_question"] = RELATION_TEMPLATES.get(relation, {}).get("question", relation)
    
    try:
        question = template.format(**template_vars)
    except KeyError:
        # Fallback if template variables don't match
        rel_phrases = [get_relation_phrase(r) for r in relations]
        question = f"{entities[0]} có liên hệ với {entities[-1]} thông qua: {' → '.join(rel_phrases)}?"
    
    return question


def generate_mcq_choices(correct_answer: str, entity_type: str, 
                        kg, num_choices: int = 4, seed: Optional[int] = None,
                        target_index: Optional[int] = None,
                        include_no_data: bool = False) -> Tuple[List[str], int]:
    """
    Generate multiple choice options for MCQ questions.
    
    Args:
        correct_answer: The correct answer (entity name)
        entity_type: Type of entity for generating distractors
        kg: KnowledgeGraph instance
        num_choices: Number of choices (default 4)
        seed: Random seed
        target_index: Optional index (0-3) to force correct answer position
        include_no_data: Whether to include "Không có dữ kiện" as a distractor
    
    Returns:
        Tuple of (choices list, correct_index)
    """
    if seed is not None:
        random.seed(seed)
    
    choices = [correct_answer]
    
    # If include_no_data is True, add "Không có dữ kiện" as a distractor
    if include_no_data:
        choices.append("Không có dữ kiện")
    
    # Handle virtual types (Year, Duration)
    if entity_type == 'Year':
        try:
            correct_year = int(correct_answer)
            while len(choices) < num_choices:
                # Generate random year within +/- 20 years
                offset = random.randint(-20, 20)
                if offset == 0: continue
                fake_year = str(correct_year + offset)
                if fake_year not in choices:
                    choices.append(fake_year)
        except ValueError:
            # Fallback if correct_answer is not a valid integer
            pass
            
    elif entity_type == 'Duration':
        # Expected format: "từ YYYY đến YYYY" or "từ YYYY"
        import re
        years = re.findall(r'\d{4}', correct_answer)
        if years:
            base_start = int(years[0])
            base_end = int(years[1]) if len(years) > 1 else None
            
            while len(choices) < num_choices:
                offset = random.randint(-10, 10)
                if offset == 0: continue
                
                fake_start = base_start + offset
                if base_end:
                    fake_end = base_end + offset
                    fake_duration = f"từ {fake_start} đến {fake_end}"
                else:
                    fake_duration = f"từ {fake_start}"
                
                if fake_duration not in choices:
                    choices.append(fake_duration)
    
    # Get other entities of same type as distractors (for normal KG types)
    if len(choices) < num_choices:
        candidate_nodes = kg.get_nodes_by_type(entity_type)
        if candidate_nodes:
            random.shuffle(candidate_nodes)
            
            for node_id in candidate_nodes:
                if len(choices) >= num_choices:
                    break
                
                node = kg.get_node(node_id)
                if node and node['name'] and node['name'] != correct_answer:
                    if node['name'] not in choices:
                        choices.append(node['name'])
    
    # If not enough distractors, add generic ones
    while len(choices) < num_choices:
        choices.append(f"[Lựa chọn giả định {len(choices)}]")
    
    # Shuffle and track correct answer
    random.shuffle(choices)
    
    # If target index provided, swap correct answer to that position
    if target_index is not None and 0 <= target_index < len(choices):
        current_idx = choices.index(correct_answer)
        if current_idx != target_index:
            choices[current_idx], choices[target_index] = choices[target_index], choices[current_idx]
            
    correct_index = choices.index(correct_answer)
    
    # Format as A), B), C), D)
    formatted_choices = [f"{chr(65+i)}) {choice}" for i, choice in enumerate(choices)]
    
    return formatted_choices, correct_index


def generate_false_statement(subject_name: str, relation: str, correct_object: str,
                            entity_type: str, kg, seed: Optional[int] = None) -> str:
    """
    Generate a false statement by replacing object with wrong entity.
    
    Args:
        subject_name: Subject entity name
        relation: Relation type
        correct_object: Correct object name
        entity_type: Type of object entity
        kg: KnowledgeGraph instance
        seed: Random seed
    
    Returns:
        False statement string
    """
    if seed is not None:
        random.seed(seed)
    
    # Find a different entity of same type
    candidate_nodes = kg.get_nodes_by_type(entity_type)
    random.shuffle(candidate_nodes)
    
    wrong_object = None
    for node_id in candidate_nodes[:20]:  # Check up to 20 candidates
        node = kg.get_node(node_id)
        if node and node['name'] and node['name'] != correct_object:
            # Verify this is actually wrong (not another correct answer)
            if not kg.verify_fact(subject_name, relation, node['name']):
                wrong_object = node['name']
                break
    
    if not wrong_object:
        wrong_object = f"[Thực thể sai]"
    
    relation_phrase = get_relation_phrase(relation)
    return f"{subject_name} {relation_phrase} {wrong_object}"


def create_question_variants(question: str, seed: Optional[int] = None) -> List[str]:
    """
    Create paraphrased variants of a question.
    
    Args:
        question: Original question
        seed: Random seed
    
    Returns:
        List of paraphrased questions
    """
    if seed is not None:
        random.seed(seed)
    
    variants = [question]
    
    # Simple paraphrasing rules (can be expanded)
    replacements = [
        ("Đúng hay sai?", "Có đúng không?"),
        ("có phải", "liệu có"),
        ("Ai/Gì", "Điều gì"),
    ]
    
    for old, new in replacements:
        if old in question:
            variant = question.replace(old, new)
            if variant not in variants:
                variants.append(variant)
    
    return variants

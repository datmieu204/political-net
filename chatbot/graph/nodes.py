# chatbot/graph/nodes.py

import os
import re
import json
from datetime import datetime, date
from typing import Dict, List, Any, Optional
from neo4j import GraphDatabase
from neo4j.time import DateTime as Neo4jDateTime, Date as Neo4jDate
from langchain_community.vectorstores import Neo4jVector

from chatbot.graph.state import ChatState
from chatbot.core.llm_client import LLMClient
from chatbot.core.embeddings import EmbeddingHuggingFace
from chatbot.semantic_router.router import ROUTER
from chatbot.core.cypher_engine import (
    build_cypher_from_intent
)
from utils.config import settings
from utils._logger import get_logger

logger = get_logger("chatbot.graph.nodes", log_file="logs/chatbot/graph/nodes.log")

def convert_neo4j_types(obj):
    if isinstance(obj, (Neo4jDateTime, Neo4jDate)):
        return obj.iso_format()
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: convert_neo4j_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_neo4j_types(item) for item in obj]
    elif hasattr(obj, '__dict__'):
        return str(obj)
    return obj

llm_client = LLMClient(
    model_name="qwen2.5:0.5b",
    temperature=0.2,
    max_tokens=668,
    history_size=10,
    streaming=False
)

slm_client = LLMClient(
    model_name="qwen-ner-0.5b-v2:latest", # qwen-ner-0.5b:latest 
    temperature=0.2,
    max_tokens=668,
    history_size=0,
    streaming=False,
    system_prompt=None,
)

embeddings = EmbeddingHuggingFace()

vector_store = Neo4jVector.from_existing_index(
    embedding=embeddings,
    url=settings.NEO4J_URI,
    username=settings.NEO4J_USER,
    password=settings.NEO4J_PASSWORD,
    database=settings.NEO4J_DATABASE,
    index_name="politician_vector_index",
    text_node_property="full_text_summary" 
)

edge_vector_store = Neo4jVector.from_existing_index(
    embedding=embeddings,
    url=settings.NEO4J_URI,
    username=settings.NEO4J_USER,
    password=settings.NEO4J_PASSWORD,
    database=settings.NEO4J_DATABASE,
    index_name="relationchunk_vector_index",
    text_node_property="text_for_embedding"
)

driver = GraphDatabase.driver(
    settings.NEO4J_URI,
    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
)

def _escape_triple_quotes(text: str) -> str:
    return text.replace('"""', '\\"\\"\\"')

# ------------------------------MAIN-------------------------------------

def semantic_router_node(state: ChatState) -> ChatState:
    user_msg = state["user_input"]
    intent_name = ROUTER.route(user_msg)
    return {"routed_intent": intent_name}

def intent_graph_node(state: ChatState) -> ChatState:
    user_msg = state["user_input"]

    node_intent = vector_store.similarity_search_with_score(user_msg, k=1)
    edge_intent = edge_vector_store.similarity_search_with_score(user_msg, k=1)

    logger.info(f"Node intent candidates: {node_intent}")
    logger.info(f"Edge intent candidates: {edge_intent}")

    THRESHOLD = 0.9

    best_score = 1.0
    graph_is_politician = False

    if node_intent:
        _, score = node_intent[0]
        if score < best_score:
            best_score = score
            graph_is_politician = True

    if edge_intent:
        _, score = edge_intent[0]
        if score < best_score:
            best_score = score
            graph_is_politician = True

    if best_score > THRESHOLD:
        graph_is_politician = False

    logger.info(
        f"[intent_graph_node] best_score={best_score:.4f} | graph_is_politician={graph_is_politician}"
    )

    return {
        "graph_is_politician": graph_is_politician,
        "graph_score": best_score,
    }

def intent_node(state: ChatState) -> ChatState:
    user_msg = state["user_input"]

    semantic_result = semantic_router_node(state)
    router_intent = semantic_result.get("routed_intent", "out_of_scope")

    # logger.info(f"[intent_node] Semantic router intent: {router_intent}")

    if router_intent == "out_of_scope":
        logger.info("[intent_node] Final intent = out_of_scope (router decision)")
        return {"intent": "out_of_scope"}

    graph_result = intent_graph_node(state)
    graph_is_politician = graph_result.get("graph_is_politician", False)
    graph_score = graph_result.get("graph_score", 1.0)

    # logger.info(f"[intent_node] Graph verification: is_politician={graph_is_politician}, score={graph_score:.4f}")

    if graph_is_politician:
        final_intent = router_intent
        logger.info(f"[intent_node] Final intent = {final_intent} (router + graph confirmed)")
    else:
        final_intent = router_intent
        logger.info(
            f"[intent_node] Final intent = {final_intent} (router says {router_intent}"
        )

    return {"intent": final_intent}

def out_of_scope_node(state: ChatState) -> ChatState:
    assistant_msg = "Xin lỗi, tôi chỉ có thể trả lời các câu hỏi liên quan đến chính trị gia Việt Nam. Vui lòng hỏi về chủ đề này."

    return {
        "assistant_output": assistant_msg,
        "history": state.get("history", [])
    }

def retrieval_node(state: ChatState) -> ChatState:
    user_msg = state["user_input"]

    node_docs = []
    edge_docs = []

    try:
        node_docs = vector_store.similarity_search(user_msg, k=5)
        # logger.info("Retrieved %d documents.", len(node_docs))
    except Exception as e:
        logger.error("Error during retrieval: %s", e)
        node_docs = []

    try:
        edge_docs = edge_vector_store.similarity_search(user_msg, k=5)
        # logger.info("Retrieved %d edge documents.", len(edge_docs))
    except Exception as e:
        logger.error("Error during retrieval of edge documents: %s", e)
        edge_docs = []

    for d in node_docs:
        d.metadata = d.metadata or {}
        d.metadata["source_type"] = "node"
    for d in edge_docs:
        d.metadata = d.metadata or {}
        d.metadata["source_type"] = "edge"

    combined_docs = node_docs + edge_docs

    return {"retrieved_documents": combined_docs}

SYSTEM_PROMPT_NER = r"""Bạn là một trợ lý AI trích xuất thực thể và quan hệ từ câu hỏi về chính trị gia Việt Nam.
Nhiệm vụ: Phân tích câu hỏi và trả về duy nhất một JSON hợp lệ theo đúng cấu trúc quy định.

QUY TẮC BẮT BUỘC:
- Chỉ in JSON, không giải thích, không thêm ghi chú.
- Không được suy diễn, không được thêm thực thể không có trong câu hỏi.
- Chỉ trích xuất tên riêng và các thực thể thuộc nhóm NODE_LABEL.
- Giữ nguyên nguyên văn entity (không viết lại, không dịch, không chuẩn hóa).
- Giữ đúng thứ tự xuất hiện của thực thể trong câu hỏi.
- Không trích xuất từ ngữ thông thường, từ để hỏi, tính từ, mệnh đề.
- Không tạo thực thể mới, không dự đoán dựa trên kiến thức bên ngoài.

NODE_LABEL hợp lệ:
  - Politician: Tên người (chính trị gia, tướng lĩnh, lãnh đạo)
  - Position: Chức vụ, chức danh
  - Location: Địa danh
  - Award: Giải thưởng, huân chương
  - MilitaryCareer: Đơn vị, lực lượng vũ trang
  - MilitaryRank: Quân hàm
  - AcademicTitle: Học hàm, học vị
  - AlmaMater: Trường học
  - Campaigns: Chiến dịch quân sự
  - TermPeriod: Thời gian (năm hoặc khoảng năm)

QUAN HỆ (EDGE_LABEL):
- PRECEDED, SUCCEEDED, BORN_AT, DIED_AT, SERVED_AS, ALUMNUS_OF, HAS_RANK, AWARDED, SERVED_IN, FOUGHT_IN, UNKNOWN.

MẪU JSON BẮT BUỘC, CHỈ TRẢ VỀ MỘT JSON:
{
  "entities": [
      {"text": "<entity>", "type": "<NODE_LABEL>"},
  ],
  "intent_relation": ["<EDGE_LABEL>"]
}
"""

alpaca_prompt = """### Instruction:
{}

### Input:
{}

### Response:
{}"""

def extract_entities_relations(question: str) -> dict:
    full_prompt = alpaca_prompt.format(
        SYSTEM_PROMPT_NER,
        question,
        ""
    )

    raw_text = slm_client.chat_without_history(
        user_input=full_prompt,
        system_override=None
    ).strip()

    try:
        start_idx = raw_text.find('{')
        if start_idx == -1:
            raise ValueError("No JSON object found in response")
        
        brace_count = 0
        end_idx = start_idx
        for i in range(start_idx, len(raw_text)):
            if raw_text[i] == '{':
                brace_count += 1
            elif raw_text[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break
        
        json_text = raw_text[start_idx:end_idx]
        
        data = json.loads(json_text)
        
        if not isinstance(data, dict):
            raise ValueError("Response is not a dictionary")
        
        if 'entities' not in data:
            data['entities'] = []
        if 'intent_relation' not in data:
            data['intent_relation'] = ["UNKNOWN"]
        
        if isinstance(data['intent_relation'], list) and len(data['intent_relation']) > 0:
            if isinstance(data['intent_relation'][0], dict):
                relation_types = list(set(item.get('type', 'UNKNOWN') for item in data['intent_relation'] if isinstance(item, dict)))
                data['intent_relation'] = relation_types if relation_types else ["UNKNOWN"]
        
        return data
        
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"JSON parsing error: {e}")
        return {
            "entities": [],
            "intent_relation": ["UNKNOWN"]
        }

def extract_entities_node(state: ChatState) -> ChatState:
    user_msg = state["user_input"]
    ner_response = extract_entities_relations(user_msg)
    logger.info(f"Parsed entities: {ner_response}")
    return {"extracted_entities": ner_response}
# -------------------------------------------------------------------------

def cypher_query_node(state: ChatState) -> ChatState:
    data = state.get("extracted_entities", {}) or {}
    user_msg = state["user_input"]
    entities = data.get("entities", [])
    intent_relation = data.get("intent_relation")

    if isinstance(intent_relation, list):
        intent_relation = intent_relation[0] if intent_relation else None
    
    logger.info(
        f"cypher_query_node | user_msg={user_msg} | intent={intent_relation} | entities={entities}"
    )


    cypher_query = build_cypher_from_intent(intent_relation=intent_relation, entities=entities)

    if not cypher_query:
        logger.warning("No Cypher query could be built from the extracted entities.")
        cypher_query = """
MATCH (p:Politician)
RETURN p.name AS name
LIMIT 5
""".strip()

    return {"cypher_query": cypher_query}

def cypher_execution_node(state: ChatState) -> ChatState:
    cypher_query = state["cypher_query"]

    with driver.session(database=settings.NEO4J_DATABASE) as session:
        try:
            result = session.run(cypher_query)
            records = result.data()
            logger.info("Executed Cypher query, got %d records.", len(records))
        except Exception as e:
            logger.error("Error executing Cypher query: %s", e)
            records = []

    # Convert Neo4j types to JSON-serializable types
    return {"subgraph": convert_neo4j_types(records)}

def graph_summary_node(state: ChatState) -> ChatState:
    subgraph = state.get("subgraph", [])
    if not subgraph:
        logger.info("graph_summary_node: empty subgraph, no data from Neo4j")
        return {"graph_summary": ""}
    user_msg = state["user_input"]

    
    instruction = "Tóm tắt thông tin từ đồ thị tri thức Neo4j về chính trị gia Việt Nam. Làm rõ mối quan hệ giữa các thực thể (ai, chức vụ gì, ở đâu, thời gian). Chỉ dùng thông tin có sẵn, không suy diễn."
    input_text = f"Câu hỏi: {user_msg}\n\nDữ liệu từ Neo4j:\n{json.dumps(subgraph[:5], ensure_ascii=False, indent=2)}"
    
    prompt = alpaca_prompt.format(instruction, input_text, "")
    summary = llm_client.chat_without_history(prompt)
    logger.info("Generated graph summary: %s", summary)
    return {"graph_summary": summary}

def retrieval_summary_node(state: ChatState) -> ChatState:
    """Tóm tắt thông tin từ vector retrieval"""
    user_msg = state["user_input"]
    retrieved_docs = state.get("retrieved_documents", [])
    
    if not retrieved_docs:
        logger.info("retrieval_summary_node: no retrieved documents")
        return {"retrieval_summary": ""}
    
    logger.info("=== retrieval_summary_node START === user_input=%r, docs=%d", user_msg, len(retrieved_docs))
    
    context = "\n\n".join([doc.page_content for doc in retrieved_docs[:5]])
    
    instruction = "Tóm tắt các thông tin liên quan đến câu hỏi từ các đoạn văn bản được truy xuất. Chỉ giữ thông tin hữu ích, loại bỏ thông tin không liên quan. Viết ngắn gọn, rõ ràng."
    input_text = f"Câu hỏi: {user_msg}\n\nVăn bản truy xuất:\n{context}"
    
    prompt = alpaca_prompt.format(instruction, input_text, "")
    summary = llm_client.chat_without_history(prompt)
    logger.info("Generated retrieval summary: %s", summary)
    return {"retrieval_summary": summary}

def combine_context_node(state: ChatState) -> ChatState:
    """Kết hợp retrieval_summary và graph_summary thành combined_context"""
    retrieval_summary = state.get("retrieval_summary", "")
    graph_summary = state.get("graph_summary", "")
        
    parts = []
    if retrieval_summary:
        parts.append(f"{retrieval_summary}")
    if graph_summary:
        parts.append(f"{graph_summary}")
    
    combined = "\n\n".join(parts) if parts else "Không có dữ liệu liên quan."
    
    logger.info("Combined context length: %d chars", len(combined))
    return {"combined_context": combined}

def tf_answer_node(state: ChatState) -> ChatState:
    user_msg = state["user_input"]
    combined_context = state.get("combined_context", "")
    
    logger.info("=== tf_answer_node context (first 500 chars): %s", combined_context[:500])
    
    instruction = "Đánh giá tính đúng/sai của câu hỏi dựa HOÀN TOÀN vào thông tin cơ sở dữ liệu. Không suy diễn. Trả lời duy nhất: 'Đúng', 'Sai', hoặc 'Không đủ thông tin'."
    input_text = f"Câu hỏi: {user_msg}\n\nCơ sở dữ liệu:\n{combined_context[:1000]}"
    
    prompt = alpaca_prompt.format(instruction, input_text, "")
    response = llm_client.chat_without_history(prompt)
    logger.info("TF response: %s", response)
    
    # Parse verdict
    verdict = "Không xác định"
    response_upper = response.upper()
    resp = response_upper.strip()
    if resp == "ĐÚNG":
        verdict = "Đúng"
    elif resp == "SAI":
        verdict = "Sai"
    elif "KHÔNG ĐỦ THÔNG TIN" in resp:
        verdict = "Không đủ thông tin"
    
    return {
        "tf_verdict": verdict,
        "tf_explanation": response,
        "assistant_output": response
    }

def mpc_parse_options_node(state: ChatState) -> ChatState:
    user_msg = state["user_input"]
    pattern = r'\b([A-D])[.)]\s*(.+?)(?=\s+[A-D][.)]\s+|$)'
    matches = re.findall(pattern, user_msg, flags=re.DOTALL)

    options = []
    for letter, content in matches:
        content = content.strip()
        content = re.sub(r'\s+', ' ', content)
        options.append(f"{letter}. {content}")
    
    logger.info("Parsed options: %s", options)
    return {"mpc_options": options}

def mpc_answer_node(state: ChatState) -> ChatState:
    user_msg = state["user_input"]
    combined_context = state.get("combined_context", "")
    mpc_options = state.get("mpc_options", [])
        
    options_str = "\n".join(mpc_options) if mpc_options else "Không tìm thấy các lựa chọn"
    
    instruction = "Chọn đáp án đúng cho câu hỏi trắc nghiệm dựa trên thông tin cơ sở dữ liệu. Trả lời duy nhất một chữ cái: A, B, C hoặc D."
    input_text = f"Câu hỏi: {user_msg}\n\nLựa chọn:\n{options_str}\n\nThông tin:\n{combined_context[:800]}"
    
    prompt = alpaca_prompt.format(instruction, input_text, "")
    response = llm_client.chat_without_history(prompt)
    logger.info("MPC response: %s", response)
    
    # Parse correct answer
    correct_answer = ""
    answer_match = re.search(r'([A-D])', response, re.IGNORECASE)
    if answer_match:
        correct_answer = answer_match.group(1).upper()
    
    return {
        "mpc_correct_answer": correct_answer,
        "mpc_explanation": response,
        "assistant_output": response
    }

# --------------------------------Multi-hop nodes---------------------------------

from chatbot.graph.multihop_config import (
    PATTERN_MAX_HOPS,
    PATTERN_KEYWORDS,
    PATTERN_DETECTION_STRATEGIES,
    PATTERN_DETECTION_WEIGHTS,
    DEFAULT_PATTERN,
    PATTERN_PRIORITY,
    DECISION_PROMPT_TEMPLATE,
    HOP_SUMMARY_TEMPLATE,
    FINAL_SUMMARY_TEMPLATE,
)

def init_multihop_node(state: ChatState) -> ChatState:
    user_msg = state["user_input"]
    
    extracted_entites = state.get("extracted_entities", {})
    entities = extracted_entites.get("entities", [])
    intent_relation = extracted_entites.get("intent_relation")

    pattern = detect_multihop_pattern(
        question=user_msg,
        entities=entities,
        intent_relation=intent_relation
    )

    max_hops = PATTERN_MAX_HOPS.get(pattern, 4)

    plan_steps: List[Dict[str, Any]] = []

    if pattern == "path":
        plan_steps = [{"type": "path"}]
        max_hops = 1
    elif pattern == "comparison":
        plan_steps = [{"type": "comparison"}]
        max_hops = 1
    elif pattern == "chain":
        plan_steps = [
            {"type": "intent"},
            {"type": "explore"},
        ]
        max_hops = len(plan_steps)
    elif pattern == "aggregation":
        plan_steps = [{"type": "intent"}]
        max_hops = len(plan_steps)
    else:
        plan_steps = [
            {"type": "intent"},
            {"type": "explore"},
            {"type": "explore"},
        ]
        max_hops = len(plan_steps)

    logger.info(f"Detected multi-hop pattern: {pattern}, max_hops: {max_hops}, plan_steps: {plan_steps}")

    return {
        "hop_count": 0,
        "max_hops": max_hops,
        "multihop_pattern": pattern,
        "multihop_params": {},
        "plan_steps": plan_steps,
        "reasoning_steps": [],
        "accumulated_context": "",
        "discovered_entities": [e.get("text", "") for e in entities if e.get("text")],
        "explored_relations": [],
        "needs_more_hops": True,
        "reasoning_complete": False,
    }


def detect_multihop_pattern(
    question: str,
    entities: List[Dict],
    intent_relation: str
) -> str:
    """
    Detect multi-hop pattern based on question, entities, and intent_relation.
    """
    
    question_lower = question.lower()

    pattern_scores = {
        "simple": 0,
        "chain": 0,
        "path": 0,
        "comparison": 0,
        "aggregation": 0,
        "explore": 0
    }

    for pattern, keywords in PATTERN_KEYWORDS.items():
        for kw in keywords:
            if re.search(kw, question_lower):
                pattern_scores[pattern] += PATTERN_DETECTION_WEIGHTS["keyword_match"]
                break

    entity_count = len(entities)
    if entity_count == 1:
        pattern_scores["simple"] += PATTERN_DETECTION_WEIGHTS["entity_count"]
    elif entity_count == 2:
        pattern_scores["path"] += PATTERN_DETECTION_WEIGHTS["entity_count"] * 0.5
        pattern_scores["comparison"] += PATTERN_DETECTION_WEIGHTS["entity_count"] * 0.5
    elif entity_count >= 3:
        pattern_scores["explore"] += PATTERN_DETECTION_WEIGHTS["entity_count"]

    intent_map = PATTERN_DETECTION_STRATEGIES["intent_relation_mapping"]
    if intent_relation:
        if isinstance(intent_relation, list):
            intent_relation = intent_relation[0] if intent_relation else None
        if intent_relation in intent_map:
            suggested_pattern = intent_map[intent_relation]
            pattern_scores[suggested_pattern] += PATTERN_DETECTION_WEIGHTS["intent_relation"]

    structure_weight = PATTERN_DETECTION_WEIGHTS["question_structure"]
    if " và " in question_lower or ", " in question_lower:
        pattern_scores["explore"] += structure_weight * 0.6

    if " hay " in question_lower or " hoặc " in question_lower:
        pattern_scores["comparison"] += structure_weight * 0.6

    if any(kw in question_lower for kw in ["đúng hay sai", "đúng không", "có phải", "có đúng"]):
        pattern_scores["explore"] += structure_weight * 0.8

    if re.search(r'[A-D][\.\)]\s+', question):
        pattern_scores["explore"] += structure_weight * 0.8

    if any(kw in question_lower for kw in ["giữa", "mối quan hệ", "liên kết"]):
        pattern_scores["path"] += structure_weight * 0.7

    if max(pattern_scores.values()) < 0.3:
        pattern_scores["explore"] += 0.5

    best_pattern, best_score = max(pattern_scores.items(), key=lambda x: x[1])

    if best_score < 0.1:
        best_pattern = DEFAULT_PATTERN

    logger.info(f"[Pattern Detection] Scores: {pattern_scores} | Selected: {best_pattern}")
    return best_pattern


def multihop_query_generator_node(state: ChatState) -> ChatState:
    """
    Tạo Cypher query cho hop tiếp theo dựa trên plan_steps và context hiện tại.
    """
    hop_count = state.get("hop_count", 0)
    max_hops = state.get("max_hops", 4)
    plan_steps = state.get("plan_steps", [])
    reasoning_steps = state.get("reasoning_steps", [])
    discovered_entities = state.get("discovered_entities", [])
    extracted_entities = state.get("extracted_entities", {})
    user_msg = state["user_input"]

    hop_count += 1
    logger.info(f"=== multihop_query_generator HOP {hop_count}/{max_hops} ===")

    if hop_count > len(plan_steps):
        logger.info(f"No more plan steps (hop_count={hop_count}, len(plan_steps)={len(plan_steps)})")
        return {"hop_count": hop_count, "cypher_query": ""}

    step = plan_steps[hop_count - 1]
    step_type = step.get("type", "explore")

    cypher_query = ""

    if step_type == "intent":
        entities = extracted_entities.get("entities", [])
        intent_relation = extracted_entities.get("intent_relation")
        if isinstance(intent_relation, list):
            intent_relation = intent_relation[0] if intent_relation else None

        cypher_query = build_cypher_from_intent(
            intent_relation=intent_relation,
            entities=entities
        )

    elif step_type == "path":
        if len(discovered_entities) >= 2:
            from chatbot.core.cypher_engine import build_path_query
            cypher_query = build_path_query(
                start_entity=discovered_entities[0],
                end_entity=discovered_entities[1],
                max_depth=4
            )

    elif step_type == "comparison":
        from chatbot.core.cypher_engine import build_comparative_query
        if discovered_entities:
            cypher_query = build_comparative_query(
                entities=discovered_entities[:3],
                attribute="birth_date",
                relation_type=None
            )

    elif step_type == "explore":
        from chatbot.core.cypher_engine import build_context_aware_query
        previous_results = []
        if reasoning_steps:
            previous_results = reasoning_steps[-1].get("result", [])
        explored_rels = state.get("explored_relations", [])

        cypher_query = build_context_aware_query(
            question=user_msg,
            previous_results=previous_results,
            hop_number=hop_count,
            max_hops=max_hops,
            explored_relations=explored_rels
        )

    if not cypher_query:
        from chatbot.core.cypher_engine import build_multihop_exploration_query
        explored_rels = state.get("explored_relations", [])
        cypher_query = build_multihop_exploration_query(
            current_entities=discovered_entities[:3],
            explored_relations=explored_rels,
            hop_number=hop_count,
            max_results=15
        )

    logger.info(f"Generated query for hop {hop_count}: {cypher_query}...")
    return {
        "hop_count": hop_count,
        "cypher_query": cypher_query
    }


def multihop_execute_node(state: ChatState) -> ChatState:
    """
    Thực thi Cypher query của hop hiện tại.
    """
    cypher_query = state.get("cypher_query", "")
    hop_count = state.get("hop_count", 0)

    logger.info(f"=== multihop_execute HOP {hop_count} ===")

    if not cypher_query:
        logger.warning(f"[HOP-{hop_count}] Empty Cypher query")
        return {"subgraph": []}

    with driver.session(database=settings.NEO4J_DATABASE) as session:
        try:
            result = session.run(cypher_query)
            records = result.data()
            logger.info(f"[HOP-{hop_count}] Executed query, got {len(records)} records")
        except Exception as e:
            logger.error(f"[HOP-{hop_count}] Error executing query: {e}")
            records = []

    return {"subgraph": convert_neo4j_types(records)}


def multihop_analyze_node(state: ChatState) -> ChatState:
    """
    Phân tích kết quả hop hiện tại và quyết định có cần hop tiếp không.
    Kết hợp logic cứng + optional LLM decision.
    """
    hop_count = state.get("hop_count", 0)
    max_hops = state.get("max_hops", 4)
    pattern = state.get("multihop_pattern", "explore")

    subgraph = state.get("subgraph", [])
    reasoning_steps = state.get("reasoning_steps", [])
    accumulated_context = state.get("accumulated_context", "")
    discovered_entities = state.get("discovered_entities", [])
    explored_relations = state.get("explored_relations", [])
    user_msg = state["user_input"]

    logger.info(f"=== multihop_analyze HOP {hop_count} ===")

    hop_summary = ""
    new_relation_types: List[str] = []
    new_entities: List[str] = []

    # ----- Tóm tắt kết quả hop hiện tại -----
    if subgraph:
        try:
            subgraph_sample = json.dumps(subgraph[:3], ensure_ascii=False, indent=2)
        except Exception:
            subgraph_sample = str(subgraph[:3])

        instruction = HOP_SUMMARY_TEMPLATE.format(
            hop_number=hop_count,
            subgraph_sample=subgraph_sample
        )
        # Dùng template làm Instruction, không cần Input
        summary_prompt = alpaca_prompt.format(instruction, "", "")
        hop_summary = llm_client.chat_without_history(summary_prompt)

        # Trích entity + relation từ result
        for record in subgraph:
            for key, value in record.items():
                # entity dạng string
                if isinstance(value, str) and len(value) > 2:
                    if key in ["name", "politician", "source_entity", "predecessor", "successor"]:
                        new_entities.append(value)
                # relation types list
                if key == "relation_types" and isinstance(value, list):
                    new_relation_types.extend(value)
                elif key.startswith("rel_") and isinstance(value, str):
                    new_relation_types.append(value)

    # update discovered_entities
    for e in new_entities:
        if e not in discovered_entities:
            discovered_entities.append(e)

    # update explored_relations
    for rel in new_relation_types:
        if rel not in explored_relations:
            explored_relations.append(rel)

    # lưu reasoning step
    reasoning_steps.append({
        "hop": hop_count,
        "query": state.get("cypher_query", ""),
        "result": subgraph,
        "summary": hop_summary
    })

    # tích lũy context
    if hop_summary:
        accumulated_context += f"\n[Bước {hop_count}] {hop_summary}"

    # ----- Quyết định dừng hay tiếp -----
    needs_more_hops = False
    reasoning_complete = False

    # 1) đạt max_hops hoặc không có kết quả -> dừng
    if hop_count >= max_hops:
        reasoning_complete = True
    elif not subgraph:
        reasoning_complete = True
    elif pattern in ("path", "comparison"):
        # các pattern này thường chỉ cần 1 hop
        reasoning_complete = True
    else:
        # pattern explore/chain:
        if not new_entities and not new_relation_types:
            reasoning_complete = True
        else:
            # Optional: hỏi LLM theo DECISION_PROMPT_TEMPLATE
            instruction = DECISION_PROMPT_TEMPLATE.format(
                question=user_msg,
                hop_count=hop_count,
                accumulated_context=accumulated_context[:800],
                max_hops=max_hops
            )
            decision_prompt = alpaca_prompt.format(instruction, "", "")
            decision = llm_client.chat_without_history(decision_prompt).strip().upper()

            if decision == "ĐỦ":
                reasoning_complete = True
            elif decision == "CHƯA ĐỦ":
                needs_more_hops = hop_count < max_hops
            else:
                # nếu model không trả lời đúng format -> dùng logic cứng
                needs_more_hops = hop_count < max_hops

    logger.info(
        f"[multihop_analyze] hop={hop_count}, pattern={pattern}, "
        f"reasoning_complete={reasoning_complete}, needs_more_hops={needs_more_hops}"
    )

    return {
        "reasoning_steps": reasoning_steps,
        "accumulated_context": accumulated_context,
        "discovered_entities": discovered_entities[:10],
        "explored_relations": explored_relations,
        "needs_more_hops": needs_more_hops,
        "reasoning_complete": reasoning_complete
    }


def multihop_should_continue(state: ChatState) -> str:
    """
    Routing: tiếp tục hop hay finalize.
    """
    needs_more = state.get("needs_more_hops", False)
    complete = state.get("reasoning_complete", False)

    if complete or not needs_more:
        return "finalize"
    return "continue"

def multihop_finalize_node(state: ChatState) -> ChatState:
    """
    Tổng hợp tất cả các bước suy luận thành graph_summary (text cho downstream).
    """
    reasoning_steps = state.get("reasoning_steps", [])
    accumulated_context = state.get("accumulated_context", "")
    user_msg = state["user_input"]

    total_hops = len([s for s in reasoning_steps if s.get("summary")])
    logger.info(f"=== multihop_finalize (total_hops={total_hops}) ===")

    steps_report = "\n".join([
        f"Bước {step['hop']}: {step.get('summary', '')}"
        for step in reasoning_steps if step.get('summary')
    ])

    instruction = FINAL_SUMMARY_TEMPLATE.format(
        question=user_msg,
        total_hops=total_hops,
        reasoning_steps=steps_report,
        accumulated_context=accumulated_context[:600]
    )
    final_prompt = alpaca_prompt.format(instruction, "", "")
    graph_summary = llm_client.chat_without_history(final_prompt)

    logger.info(f"Finalized multi-hop reasoning with {total_hops} steps")
    return {
        "graph_summary": graph_summary
    }

# -------------------------------------------------------------------------
if __name__ == "__main__":
    # test_state = {"user_input": "Nguyễn Phú Trọng quê ở đâu ? A. quê Hà Nội B. sinh năm 1944 C. học ở Đại học Tổng hợp Hà Nội"}
    # result_state = intent_node(test_state)
    # print(result_state)

    # ----------------------------------------------------------------
    # test retrieval_node
    # test_state = {"user_input": "Nguyễn Xuân Phúc sinh ra ở đâu?"}
    # result_state = retrieval_node(test_state)
    # for doc in result_state["retrieved_documents"]:
    #     print(doc.page_content)

    # ----------------------------------------------------------------
    # test cypher node
    # test_state = {
    #     "user_input": "Nguyễn Xuân Phúc sinh ra ở đâu?",
    #     "extracted_entities": {
    #         "entities": [
    #             {"text": "Nguyễn Xuân Phúc", "type": "Politician"}
    #         ],
    #         "intent_relation": "BORN_AT"
    #     }
    # }

    # result_state = cypher_query_node(test_state)
    # print(result_state)
    # result_state = cypher_execution_node(result_state)
    # print(result_state)

    # ----------------------------------------------------------------
    # test extract_entities_node

    # test_state = {
    #     "user_input": "Ông Nguyễn Phú Trọng sinh năm bao nhiêu, học ở đâu và giữ chức vụ gì hiện nay?"
    # }
    # result_state = extract_entities_node(test_state)
    # print(result_state)


    test_state = {
        "user_input": "Tô Lâm sinh ra ở Hà Nội có đúng không ?"
    }

    result_state = extract_entities_node(test_state)
    print(result_state)
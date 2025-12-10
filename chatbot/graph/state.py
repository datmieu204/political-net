# chatbot/graph/state.py

from typing import TypedDict, List, Optional, Any, Dict, Literal

class ChatState(TypedDict, total=False):
    user_input: str

    # Intent
    intent: Literal["politician_tf", "politician_mpc", "out_of_scope"]
    routed_intent: str
    graph_is_politician: bool
    graph_score: float

    # Vector RAG
    retrieved_documents: List[Any]
    retrieval_summary: str

    # GraphRAG
    extracted_entities: Dict[str, Any]
    cypher_query: str
    subgraph: List[Dict[str, Any]]
    graph_summary: str

    combined_context: str

    # Multi-hop reasoning
    hop_count: int
    max_hops: int
    
    multihop_pattern: str
    multihop_params: Dict[str, Any]
    plan_steps: List[Dict[str, Any]]
    
    reasoning_steps: List[Dict[str, Any]]
    accumulated_context: str
    discovered_entities: List[str]
    explored_relations: List[str]
    
    needs_more_hops: bool
    reasoning_complete: bool

    # True/False question
    tf_statement: str
    tf_verdict: str
    tf_explanation: str

    # Multiple Choice question
    mpc_options: List[str]
    mpc_correct_answer: str
    mpc_explanation: str

    # Chatbot
    assistant_output: str
    history: List[dict]
# chatbot/graph/graph.py

from langgraph.graph import StateGraph, END
from chatbot.graph.state import ChatState
from chatbot.graph.nodes import (
    retrieval_node, 
    intent_node,
    out_of_scope_node,
    extract_entities_node,
    graph_summary_node,
    retrieval_summary_node,
    combine_context_node,
    tf_answer_node,
    mpc_parse_options_node,
    mpc_answer_node,
    # Multi-hop nodes
    init_multihop_node,
    multihop_query_generator_node,
    multihop_execute_node,
    multihop_analyze_node,
    multihop_should_continue,
    multihop_finalize_node
)

def route_intent(state: ChatState) -> str:
    intent = state.get("intent", "out_of_scope")
    if intent == "politician_tf":
        return "politician_tf"
    elif intent == "politician_mpc":
        return "politician_mpc"
    return "out_of_scope"

def build_chatgraph() -> StateGraph[ChatState]:
    graph = StateGraph(ChatState)

    # ========================= NODES =========================
    graph.add_node("intent", intent_node)
    graph.add_node("out_of_scope", out_of_scope_node)
    graph.add_node("extract_entities", extract_entities_node)
    graph.add_node("retrieval", retrieval_node)
    # Multi-hop reasoning nodes
    graph.add_node("init_multihop", init_multihop_node)
    graph.add_node("multihop_query", multihop_query_generator_node)
    graph.add_node("multihop_execute", multihop_execute_node)
    graph.add_node("multihop_analyze", multihop_analyze_node)
    graph.add_node("multihop_finalize", multihop_finalize_node)
    graph.add_node("retrieval_summary", retrieval_summary_node)
    graph.add_node("combine_context", combine_context_node)
    # Answer nodes for different intents
    graph.add_node("tf_answer", tf_answer_node)
    graph.add_node("mpc_parse_options", mpc_parse_options_node)
    graph.add_node("mpc_answer", mpc_answer_node)

    graph.set_entry_point("intent")
    graph.add_conditional_edges(
        "intent",
        route_intent,
        {
            "politician_tf": "extract_entities",
            "politician_mpc": "extract_entities", 
            "out_of_scope": "out_of_scope"
        }
    )

    # extract_entities -> retrieval -> retrieval_summary -> init_multihop
    graph.add_edge("extract_entities", "retrieval")
    graph.add_edge("retrieval", "retrieval_summary")
    graph.add_edge("retrieval_summary", "init_multihop")
    
    # Multi-hop loop
    graph.add_edge("init_multihop", "multihop_query")
    graph.add_edge("multihop_query", "multihop_execute")
    graph.add_edge("multihop_execute", "multihop_analyze")
    
    # Conditional: continue hopping or finalize
    graph.add_conditional_edges(
        "multihop_analyze",
        multihop_should_continue,
        {
            "continue": "multihop_query",
            "finalize": "multihop_finalize"
        }
    )
    
    graph.add_edge("multihop_finalize", "combine_context")

    def route_to_answer(state: ChatState) -> str:
        intent = state.get("intent", "out_of_scope")
        if intent == "politician_tf":
            return "tf_answer"
        elif intent == "politician_mpc":
            return "mpc_parse_options"
        else:
            return "out_of_scope"
    
    graph.add_conditional_edges(
        "combine_context",
        route_to_answer,
        {
            "tf_answer": "tf_answer",
            "mpc_parse_options": "mpc_parse_options",
            "out_of_scope": "out_of_scope"
        }
    )
    
    graph.add_edge("mpc_parse_options", "mpc_answer")

    graph.add_edge("out_of_scope", END)
    graph.add_edge("tf_answer", END)
    graph.add_edge("mpc_answer", END)

    return graph.compile()
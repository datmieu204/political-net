# chatbot/core/workflow.py

from chatbot.graph.graph import build_chatgraph

chatbot_graph = build_chatgraph()

def run_chatbot_workflow(user_input: str, history: list = None) -> dict:
    initial_state = {
        "user_input": user_input,
    }
    if history:
        initial_state["history"] = history

    final_state = chatbot_graph.invoke(initial_state)

    return {
        "assistant_output": final_state.get("assistant_output", ""),
        "history": final_state.get("history", [])
    }
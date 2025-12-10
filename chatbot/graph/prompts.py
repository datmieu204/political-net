# chatbot/graph/prompts.py

intent_prompt_template = """Given the user message, determine the intent category it belongs to from the following options: 'POLICIAN' or 'OTHER'."""

extract_prompt_template = """You are provided with the following documents retrieved based on the user's query. Extract relevant information from these documents to help answer the user's question accurately and concisely."""

final_answer_prompt_template = """Using the extracted information, provide a clear and concise answer to the user's question. Ensure that the answer is relevant and directly addresses the user's query."""

graph_summary_prompt_template = """Summarize the content of the graph nodes and relationships to provide a brief overview that can assist in answering user queries effectively."""
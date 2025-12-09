# chatbot/run_chatbot.py

from chatbot.graph.workflow import run_chatbot_workflow

history = []

while True:
    user_input = input("You: ")
    if user_input.lower() in {"exit", "quit"}:
        print("Exiting chat...")
        break

    result = run_chatbot_workflow(user_input, history)
    assistant_output = result["assistant_output"]
    history = result["history"]

    print(f"Assistant: {assistant_output}\n")
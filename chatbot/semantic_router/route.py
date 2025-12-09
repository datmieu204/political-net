# chatbot/semantic_router/route.py

class Route:
    def __init__(self, name: str, intent=None):
        self.name = name
        self.intent = intent if intent else []
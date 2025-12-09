# chatbot/core/llm_client.py

from typing import Optional, List, Dict
from dotenv import load_dotenv
load_dotenv()

from langchain_ollama import ChatOllama
from langchain.schema import HumanMessage, AIMessage, SystemMessage

class LLMClient:
    def __init__(
        self, 
        model_name: str = "qwen2.5:0.5b",
        temperature: float = 0.2,
        max_tokens: int = 512,
        history_size: int = 5,
        streaming: bool = False,
        system_prompt: Optional[str] = None,
    ):
        self.history_size = history_size
        self.chat_history = []
        self.system_prompt = system_prompt

        self.llm = ChatOllama(
            model=model_name,
            temperature=temperature,
            num_predict=max_tokens,
            streaming=streaming
        )

    def _build_messages(self, user_input: str, system_override: Optional[str] = None):
        """
        Build messages với SystemMessage + History + HumanMessage.
        
        Args:
            user_input: question from user
            system_override: Override system prompt if needed (for specific tasks)
        """
        messages = []
        
        system_content = system_override or self.system_prompt

        if system_content:
            messages.append(SystemMessage(content=system_content))

        for item in self.chat_history[-self.history_size:]:
            if item["role"] == "user":
                messages.append(HumanMessage(content=item["content"]))
            elif item["role"] == "assistant":
                messages.append(AIMessage(content=item["content"]))

        messages.append(HumanMessage(content=user_input))
        
        return messages

    def chat(self, user_input: str, system_override: Optional[str] = None) -> str:
        """
        Main chat method with history.
        
        Args:
            user_input: User's question/prompt
            system_override: Optional system prompt override for specific tasks
        """
        messages = self._build_messages(user_input, system_override)
        response = self.llm.invoke(messages)
        assistant_reply = response.content

        self.chat_history.append({"role": "user", "content": user_input})
        self.chat_history.append({"role": "assistant", "content": assistant_reply})

        return assistant_reply
    
    def chat_without_history(self, user_input: str, system_override: Optional[str] = None) -> str:
        """
        Chat without adding to history.
        
        Args:
            user_input: User's question/prompt
            system_override: Optional system prompt override
        """
        messages = []
        
        system_content = system_override or self.system_prompt

        if system_content:
            messages.append(SystemMessage(content=system_content))
        messages.append(HumanMessage(content=user_input))
        
        response = self.llm.invoke(messages)
        return response.content
    
    def clear_history(self):
        """Clear chat history."""
        self.chat_history = []
    
    def set_system_prompt(self, prompt: str):
        """Update system prompt."""
        self.system_prompt = prompt

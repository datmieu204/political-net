# chatbot/semantic_router/router_faiss.py

import os
from typing import Dict, List, Optional
from langchain_community.vectorstores import FAISS
from langchain.docstore.document import Document
from chatbot.semantic_router.intent import other_intent, polician_tf_intent, polician_mpc_intent
from chatbot.semantic_router.route import Route

from chatbot.core.embeddings import EmbeddingHuggingFace
from chatbot.semantic_router.route import Route

class SemanticRouterFAISS:
    def __init__(
        self,
        embedding: EmbeddingHuggingFace,
        intents: Dict[str, Route],
        faiss_index_path: Optional[str] = None
    ):
        self.embedding = embedding
        self.intents = intents
        self.faiss_index_path = faiss_index_path

        if faiss_index_path and os.path.exists(faiss_index_path):
            self.vector_store = FAISS.load_local(
                faiss_index_path, 
                embeddings=embedding,
                allow_dangerous_deserialization=True,
                # safe=True
            )
        else:
            documents: List[Document] = []
            for intent_key, route in intents.items():
                for text in route.intent:
                    documents.append(Document(
                        page_content=text,
                        metadata={"intent_name": intent_key}
                    ))
            self.vector_store = FAISS.from_documents(documents=documents, embedding=embedding)

            if faiss_index_path:
                self.vector_store.save_local(
                    faiss_index_path,
                    # safe=True
                )

    def route(self, query: str, k: int = 1) -> str:
        """
        Route query to the most relevant intent using FAISS similarity search.
        query: user question
        k: number of top-k results to retrieve, default is 1
        return: intent_name
        """
        results = self.vector_store.similarity_search(query, k=k)
        if results:
            return results[0].metadata["intent_name"]
        return "UNKNOWN"

    def save(self, path: str):
        self.vector_store.save_local(path)

    def load(self, path: str):
        self.vector_store = FAISS.load_local(path, embedding=self.embedding)

intents = {
    "politician_tf": Route("politician_tf", polician_tf_intent),
    "politician_mpc": Route("politician_mpc", polician_mpc_intent),
    "out_of_scope": Route("out_of_scope", other_intent)
}

embedding = EmbeddingHuggingFace()

ROUTER = SemanticRouterFAISS(
    embedding=embedding,
    intents=intents,
    faiss_index_path="semantic_router_faiss_index"
)
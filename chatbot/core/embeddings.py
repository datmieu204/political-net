# chatbot/core/embeddings.py

import torch
from typing import Optional
from langchain_huggingface import HuggingFaceEmbeddings

from utils._logger import get_logger
from utils.config import settings

logger = get_logger("chatbot.core.embeddings", log_file="logs/chatbot/core/embeddings.log")

def get_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    elif torch.backends.mps.is_available():
        return "mps"
    else:
        return "cpu"
    
class EmbeddingHuggingFace:
    def __init__(
        self, 
        model_name: str = None,
        device: Optional[str] = None,
        normalize_embeddings: bool = True,
        show_progress: bool = True,
        extra_model_kwargs: Optional[dict[str, any]] = None,
        extra_encode_kwargs: Optional[dict[str, any]] = None 
    ) -> None:
        
        self.model_name = model_name if model_name else settings.EMBEDDING_MODEL_NAME
        self.device = device if device else get_device()
        self.normalize_embeddings = normalize_embeddings
        self.extra_model_kwargs = extra_model_kwargs if extra_model_kwargs else {}
        self.extra_encode_kwargs = extra_encode_kwargs if extra_encode_kwargs else {}

        model_kwargs = {'device': self.device}
        model_kwargs.update(self.extra_model_kwargs)
        encode_kwargs = {'normalize_embeddings': self.normalize_embeddings}
        encode_kwargs.update(self.extra_encode_kwargs)

        try:
            self.huggingface_embeddings = HuggingFaceEmbeddings(
                model_name=self.model_name,
                model_kwargs=model_kwargs,
                encode_kwargs=encode_kwargs,
                show_progress=show_progress
            )
            logger.info(f"HuggingFaceEmbeddings initialized with model: {self.model_name} on device: {self.device}")
        except Exception as e:
            logger.error(f"Error initializing HuggingFaceEmbeddings: {e}", exc_info=True)
            raise e

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a list of documents (texts) into their vector representations.
        """
        return self.huggingface_embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        """
        Embed a single query (text) into its vector representation.
        """
        return self.huggingface_embeddings.embed_query(text)
    
    def __call__(self, text: str) -> list[float]:
        return self.embed_query(text)

# device = get_device()
# logger.info(f"Using device for embeddings: {device}")

# model_name = settings.EMBEDDING_MODEL_NAME
# model_kwargs = {'device': device}
# encode_kwargs = {'normalize_embeddings': True}

# try:
#     huggingface_embeddings = HuggingFaceEmbeddings(
#         model_name=model_name,
#         model_kwargs=model_kwargs,
#         encode_kwargs=encode_kwargs,
#         show_progress=True
#     )
#     logger.info(f"HuggingFaceEmbeddings initialized with model: {model_name}")
# except Exception as e:
#     logger.error(f"Error initializing HuggingFaceEmbeddings: {e}", exc_info=True)
#     raise e

# embeddings = huggingface_embeddings
from langchain_community.embeddings import OllamaEmbeddings
from app.core.config import settings

def get_embeddings() -> OllamaEmbeddings:
    return OllamaEmbeddings(
        base_url=settings.ollama_host,
        model=settings.embed_model,
    )

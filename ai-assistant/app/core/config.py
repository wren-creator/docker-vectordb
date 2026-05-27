import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Qdrant
    qdrant_host: str = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port: int = int(os.getenv("QDRANT_PORT", 6333))
    code_collection: str = os.getenv("CODE_COLLECTION", "code_knowledge")
    docs_collection: str = os.getenv("DOCS_COLLECTION", "doc_knowledge")

    # Redis
    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", 6379))
    conversation_ttl: int = int(os.getenv("CONVERSATION_TTL", 86400))

    # Ollama
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    embed_model: str = os.getenv("EMBED_MODEL", "nomic-embed-text")
    llm_model: str = os.getenv("LLM_MODEL", "llama3")

    # Scheduler
    sync_interval_minutes: int = int(os.getenv("SYNC_INTERVAL_MINUTES", 15))

    # Paths
    repos_config: str = "/app/repos.yml"
    repos_cache: str = "/app/repos_cache"
    data_dir: str = "/app/data"

settings = Settings()

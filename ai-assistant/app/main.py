from fastapi import FastAPI
from app.routers.api import router

app = FastAPI(
    title="On-Prem AI Assistant — RAG API",
    description="Code + doc knowledge base with conversation memory. Powered by Qdrant + Ollama.",
    version="1.0.0",
)

app.include_router(router)

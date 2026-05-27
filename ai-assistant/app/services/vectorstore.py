from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from langchain_qdrant import QdrantVectorStore
from app.services.embeddings import get_embeddings
from app.core.config import settings

VECTOR_SIZE = 768  # nomic-embed-text


def get_qdrant_client() -> QdrantClient:
    return QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)


def ensure_collection(client: QdrantClient, name: str):
    existing = [c.name for c in client.get_collections().collections]
    if name not in existing:
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        print(f"[qdrant] Created collection: {name}")


def get_vectorstore(collection: str) -> QdrantVectorStore:
    client = get_qdrant_client()
    ensure_collection(client, collection)
    return QdrantVectorStore(
        client=client,
        collection_name=collection,
        embedding=get_embeddings(),
    )


def get_code_vectorstore() -> QdrantVectorStore:
    return get_vectorstore(settings.code_collection)


def get_docs_vectorstore() -> QdrantVectorStore:
    return get_vectorstore(settings.docs_collection)


def collection_stats() -> dict:
    client = get_qdrant_client()
    result = {}
    for name in [settings.code_collection, settings.docs_collection]:
        try:
            info = client.get_collection(name)
            result[name] = {
                "vectors_count": info.vectors_count,
                "status": str(info.status),
            }
        except Exception:
            result[name] = {"vectors_count": 0, "status": "not_found"}
    return result

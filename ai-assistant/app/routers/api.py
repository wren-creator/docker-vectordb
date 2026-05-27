import os, shutil, uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from app.services.doc_ingest import ingest_document, ingest_documents_directory
from app.services.code_ingest import ingest_repo_directory
from app.services.repo_manager import sync_all_repos, sync_repo, load_repos_config
from app.services.vectorstore import get_code_vectorstore, get_docs_vectorstore, collection_stats
from app.services.memory import save_message, load_history, clear_session
from app.services.prompt_builder import build_system_prompt
from app.core.config import settings
import ollama

router = APIRouter()
UPLOAD_DIR = "/app/data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ══════════════════════════════════════════════════════════
#  HEALTH & STATS
# ══════════════════════════════════════════════════════════

@router.get("/health")
def health():
    return {"status": "ok"}

@router.get("/stats")
def stats():
    return {"collections": collection_stats()}


# ══════════════════════════════════════════════════════════
#  DOCUMENT INGESTION
# ══════════════════════════════════════════════════════════

@router.post("/ingest/document/upload")
async def ingest_doc_upload(file: UploadFile = File(...)):
    dest = os.path.join(UPLOAD_DIR, file.filename)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        chunks = ingest_document(dest)
        return {"file": file.filename, "chunks_ingested": chunks}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/ingest/document/directory")
def ingest_doc_dir(directory: str = "/app/data/documents"):
    return {"results": ingest_documents_directory(directory)}


# ══════════════════════════════════════════════════════════
#  REPO INGESTION
# ══════════════════════════════════════════════════════════

@router.post("/ingest/repos/sync-all")
def sync_all():
    """Trigger immediate sync of all repos defined in repos.yml."""
    results = sync_all_repos()
    return {"results": results}

@router.post("/ingest/repos/sync/{repo_name}")
def sync_one(repo_name: str):
    """Trigger immediate sync of a single named repo."""
    config = load_repos_config()
    global_cfg = config.get("global", {})
    repos = {r["name"]: r for r in config.get("repos", [])}
    if repo_name not in repos:
        raise HTTPException(status_code=404, detail=f"Repo '{repo_name}' not found in repos.yml")
    result = sync_repo(repos[repo_name], global_cfg)
    return result

@router.get("/ingest/repos/list")
def list_repos():
    config = load_repos_config()
    return {"repos": [r["name"] for r in config.get("repos", [])]}


# ══════════════════════════════════════════════════════════
#  SEARCH / QUERY
# ══════════════════════════════════════════════════════════

class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    collection: str = "code"   # "code" | "docs" | "both"

@router.post("/query")
def query(req: QueryRequest):
    results = []
    if req.collection in ("code", "both"):
        docs = get_code_vectorstore().similarity_search_with_score(req.query, k=req.top_k)
        for doc, score in docs:
            results.append({"source": "code", "score": round(float(score), 4),
                            "content": doc.page_content, "metadata": doc.metadata})
    if req.collection in ("docs", "both"):
        docs = get_docs_vectorstore().similarity_search_with_score(req.query, k=req.top_k)
        for doc, score in docs:
            results.append({"source": "docs", "score": round(float(score), 4),
                            "content": doc.page_content, "metadata": doc.metadata})
    results.sort(key=lambda x: x["score"], reverse=True)
    return {"query": req.query, "results": results}


# ══════════════════════════════════════════════════════════
#  CHAT  (full RAG + memory)
# ══════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None   # omit to start a new session

class ChatResponse(BaseModel):
    session_id: str
    response: str

@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())

    # Build dynamic system prompt with retrieved context + memory
    system_prompt = build_system_prompt(req.message, session_id)

    # Load prior turns for multi-turn conversation
    history = load_history(session_id)
    messages = [
        {"role": m["role"], "content": m["content"]}
        for m in history
        if m["role"] in ("user", "assistant")
    ]
    messages.append({"role": "user", "content": req.message})

    # Call Ollama
    response = ollama.chat(
        model=settings.llm_model,
        messages=[{"role": "system", "content": system_prompt}] + messages,
    )
    answer = response["message"]["content"]

    # Persist to memory
    save_message(session_id, "user", req.message)
    save_message(session_id, "assistant", answer)

    return ChatResponse(session_id=session_id, response=answer)


# ══════════════════════════════════════════════════════════
#  MEMORY MANAGEMENT
# ══════════════════════════════════════════════════════════

@router.get("/memory/{session_id}")
def get_memory(session_id: str):
    return {"session_id": session_id, "history": load_history(session_id)}

@router.delete("/memory/{session_id}")
def delete_memory(session_id: str):
    clear_session(session_id)
    return {"session_id": session_id, "status": "cleared"}

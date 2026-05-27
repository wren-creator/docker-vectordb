import os
from pathlib import Path
from datetime import datetime
from langchain_community.document_loaders import PyPDFLoader, TextLoader, UnstructuredMarkdownLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from app.services.vectorstore import get_docs_vectorstore

SUPPORTED = {".pdf", ".txt", ".md"}


def get_loader(file_path: str):
    ext = Path(file_path).suffix.lower()
    loaders = {
        ".pdf": PyPDFLoader,
        ".txt": TextLoader,
        ".md":  UnstructuredMarkdownLoader,
    }
    cls = loaders.get(ext)
    if not cls:
        raise ValueError(f"Unsupported file type: {ext}")
    return cls(file_path)


def ingest_document(file_path: str, chunk_size: int = 512, chunk_overlap: int = 64) -> int:
    loader = get_loader(file_path)
    docs = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    chunks = splitter.split_documents(docs)

    filename = Path(file_path).name
    for chunk in chunks:
        chunk.metadata.update({
            "file":        filename,
            "source_type": "document",
            "ingested_at": datetime.utcnow().isoformat(),
        })

    vs = get_docs_vectorstore()
    vs.add_documents(chunks)
    return len(chunks)


def ingest_documents_directory(directory: str = "/app/data/documents") -> dict:
    results = {}
    for path in Path(directory).rglob("*"):
        if path.suffix.lower() in SUPPORTED:
            try:
                count = ingest_document(str(path))
                results[path.name] = {"chunks": count, "status": "ok"}
            except Exception as e:
                results[path.name] = {"error": str(e), "status": "failed"}
    return results

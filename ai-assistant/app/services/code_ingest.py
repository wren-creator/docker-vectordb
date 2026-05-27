import os
import fnmatch
from pathlib import Path
from datetime import datetime
from langchain.text_splitter import Language, RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain.schema import Document
from app.services.vectorstore import get_code_vectorstore
from app.core.config import settings

# ── Language map ──────────────────────────────────────────────────────────────
LANGUAGE_MAP: dict[str, Language] = {
    ".py":    Language.PYTHON,
    ".js":    Language.JS,
    ".jsx":   Language.JS,
    ".ts":    Language.TS,
    ".tsx":   Language.TS,
    ".go":    Language.GO,
    ".rs":    Language.RUST,
    ".java":  Language.JAVA,
    ".c":     Language.C,
    ".cpp":   Language.CPP,
    ".rb":    Language.RUBY,
    ".kt":    Language.KOTLIN,
    ".swift": Language.SWIFT,
    ".scala": Language.SCALA,
}

CODE_EXTENSIONS = set(LANGUAGE_MAP.keys()) | {".sh", ".yaml", ".yml", ".toml", ".tf"}


def is_excluded(path: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if fnmatch.fnmatch(path, pattern):
            return True
    return False


def get_splitter(ext: str, chunk_size: int = 400, chunk_overlap: int = 60):
    lang = LANGUAGE_MAP.get(ext)
    if lang:
        return RecursiveCharacterTextSplitter.from_language(
            language=lang,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    # Fallback for shell/yaml/toml etc.
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


def ingest_code_file(
    file_path: str,
    repo_name: str,
    repo_root: str,
    chunk_size: int = 400,
    chunk_overlap: int = 60,
) -> int:
    ext = Path(file_path).suffix.lower()
    if ext not in CODE_EXTENSIONS:
        return 0

    try:
        loader = TextLoader(file_path, encoding="utf-8", autodetect_encoding=True)
        docs = loader.load()
    except Exception as e:
        print(f"[ingest] Could not load {file_path}: {e}")
        return 0

    splitter = get_splitter(ext, chunk_size, chunk_overlap)
    chunks = splitter.split_documents(docs)

    relative_path = os.path.relpath(file_path, repo_root)

    enriched: list[Document] = []
    for chunk in chunks:
        chunk.metadata.update({
            "repo":        repo_name,
            "file":        relative_path,
            "language":    ext.lstrip("."),
            "source_type": "code",
            "ingested_at": datetime.utcnow().isoformat(),
        })
        enriched.append(chunk)

    if enriched:
        vs = get_code_vectorstore()
        vs.add_documents(enriched)

    return len(enriched)


def ingest_repo_directory(
    repo_path: str,
    repo_name: str,
    exclude_patterns: list[str] | None = None,
    chunk_size: int = 400,
    chunk_overlap: int = 60,
    changed_files: list[str] | None = None,   # None = full ingest
) -> dict:
    patterns = exclude_patterns or []
    results = {"files_processed": 0, "chunks_ingested": 0, "errors": []}

    if changed_files is not None:
        # Incremental — only re-index changed files
        file_paths = [
            os.path.join(repo_path, f)
            for f in changed_files
            if Path(f).suffix.lower() in CODE_EXTENSIONS
        ]
    else:
        # Full ingest
        file_paths = [
            str(p)
            for p in Path(repo_path).rglob("*")
            if p.is_file() and p.suffix.lower() in CODE_EXTENSIONS
        ]

    for file_path in file_paths:
        relative = os.path.relpath(file_path, repo_path)
        if is_excluded(relative, patterns):
            continue
        try:
            count = ingest_code_file(file_path, repo_name, repo_path, chunk_size, chunk_overlap)
            results["files_processed"] += 1
            results["chunks_ingested"] += count
        except Exception as e:
            results["errors"].append({"file": relative, "error": str(e)})

    return results

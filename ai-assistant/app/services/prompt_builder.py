from app.services.vectorstore import get_code_vectorstore, get_docs_vectorstore
from app.services.memory import format_history_for_prompt


def build_system_prompt(query: str, session_id: str | None = None) -> str:
    """
    Retrieve relevant context from all sources and build
    a rich system prompt for the LLM.
    """

    # ── 1. Code context ───────────────────────────────────────────
    code_context = ""
    try:
        code_vs = get_code_vectorstore()
        code_docs = code_vs.similarity_search(query, k=5)
        if code_docs:
            sections = []
            for doc in code_docs:
                meta = doc.metadata
                header = f"### [{meta.get('repo', '?')}] {meta.get('file', '?')} ({meta.get('language', '?')})"
                sections.append(f"{header}\n```{meta.get('language', '')}\n{doc.page_content}\n```")
            code_context = "\n\n".join(sections)
    except Exception as e:
        code_context = f"(Code retrieval unavailable: {e})"

    # ── 2. Documentation context ──────────────────────────────────
    doc_context = ""
    try:
        doc_vs = get_docs_vectorstore()
        doc_docs = doc_vs.similarity_search(query, k=2)
        if doc_docs:
            sections = []
            for doc in doc_docs:
                meta = doc.metadata
                header = f"### {meta.get('file', 'Document')}"
                sections.append(f"{header}\n{doc.page_content}")
            doc_context = "\n\n".join(sections)
    except Exception as e:
        doc_context = f"(Doc retrieval unavailable: {e})"

    # ── 3. Conversation memory ────────────────────────────────────
    memory_context = ""
    if session_id:
        try:
            memory_context = format_history_for_prompt(session_id, k=4)
        except Exception as e:
            memory_context = f"(Memory unavailable: {e})"

    # ── 4. Assemble prompt ────────────────────────────────────────
    prompt_parts = [
        "You are a senior software engineer assistant with deep knowledge of this organization's codebase.",
        "You answer questions using the actual code and patterns from the repositories indexed below.",
        "Always reference specific files and functions when relevant.",
        "Match the coding style and conventions you observe in the retrieved code.",
        "If the context does not contain enough information to answer confidently, say so.",
        "",
    ]

    if code_context:
        prompt_parts += [
            "## Relevant code from the codebase",
            code_context,
            "",
        ]

    if doc_context:
        prompt_parts += [
            "## Relevant internal documentation",
            doc_context,
            "",
        ]

    if memory_context:
        prompt_parts += [
            "## Recent conversation history",
            memory_context,
            "",
        ]

    prompt_parts += [
        "## Behavior guidelines",
        "- Cite the repo and file path when referencing code",
        "- Prefer internal patterns over generic solutions",
        "- Flag any security anti-patterns you notice",
        "- Be concise but thorough",
    ]

    return "\n".join(prompt_parts)

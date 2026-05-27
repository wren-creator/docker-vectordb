# On-Prem AI Assistant — RAG Stack

A fully self-hosted AI engineering assistant that indexes your code repositories and documents,
stores them in a vector database, and answers questions using your own LLM via Ollama or vLLM.
Nothing leaves your network.

---

## Stack

| Component     | Role                                      |
|---------------|-------------------------------------------|
| **Qdrant**    | Vector database (code + doc collections)  |
| **Redis**     | Conversation memory (per session)         |
| **FastAPI**   | RAG API (ingest, query, chat)             |
| **Scheduler** | Periodic git repo sync                    |
| **Ollama**    | Embeddings (nomic-embed-text) + LLM       |

---

## Prerequisites

```bash
# Ollama must be running on your host with these models pulled
ollama pull nomic-embed-text
ollama pull llama3          # or whichever LLM you prefer
```

---

## Quick Start

```bash
# 1. Clone / copy this project
cd ai-assistant

# 2. Edit repos.yml — point it at your git repos
nano repos.yml

# 3. Create required directories
mkdir -p qdrant_storage redis_data data/{documents,uploads,repos} repos_cache

# 4. Build and start everything
docker compose up --build

# 5. Check health
curl http://localhost:8000/health

# 6. Check collection stats
curl http://localhost:8000/stats
```

---

## Adding Your Repos

Edit `repos.yml`. Two types are supported:

### Local repo (already on disk)
```yaml
repos:
  - name: my-backend
    type: local
    path: /app/data/repos/my-backend
    branch: main
```
Mount the parent directory in `docker-compose.yml`:
```yaml
volumes:
  - /home/youruser/projects:/app/data/repos
```

### Remote repo (GitHub / GitLab / Gitea)
```yaml
repos:
  - name: backend-api
    type: remote
    url: https://github.com/myorg/backend-api.git
    branch: main
    auth: token
    token_env: GITHUB_TOKEN
```
Add the token to `docker-compose.yml` environment:
```yaml
environment:
  - GITHUB_TOKEN=ghp_yourtoken
```

---

## API Reference

### Ingest

| Method | Endpoint                          | Description                        |
|--------|-----------------------------------|------------------------------------|
| POST   | `/ingest/document/upload`         | Upload a PDF, TXT, or MD file      |
| POST   | `/ingest/document/directory`      | Ingest all docs from a directory   |
| POST   | `/ingest/repos/sync-all`          | Trigger immediate sync of all repos|
| POST   | `/ingest/repos/sync/{repo_name}`  | Sync a single named repo           |
| GET    | `/ingest/repos/list`              | List configured repos              |

### Query & Chat

| Method | Endpoint            | Description                                    |
|--------|---------------------|------------------------------------------------|
| POST   | `/query`            | Raw vector search (code, docs, or both)        |
| POST   | `/chat`             | Full RAG chat with memory                      |
| GET    | `/memory/{id}`      | View conversation history for a session        |
| DELETE | `/memory/{id}`      | Clear a session's memory                       |
| GET    | `/stats`            | Collection vector counts                       |

### Chat Example

```bash
# Start a new session
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "How does authentication work in this codebase?"}'

# Continue the session (use the session_id from the response)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Show me where tokens are validated", "session_id": "abc-123"}'
```

### Query Example

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "database connection pooling", "collection": "code", "top_k": 5}'
```

---

## How the System Prompt Works

Every `/chat` request dynamically builds a system prompt by:

1. Querying Qdrant for the **top 5 most relevant code chunks**
2. Querying Qdrant for the **top 2 most relevant doc chunks**
3. Loading the **last 4 exchanges** from Redis for this session
4. Assembling them into a structured prompt before calling the LLM

This means the AI always answers using **your actual code**, not generic examples.

---

## Repo Sync Schedule

The scheduler container polls all repos every `sync_interval_minutes` (default: 15).

- **First run**: full ingest of every file
- **Subsequent runs**: only changed files (via `git diff`) are re-indexed

Force an immediate sync via the API:
```bash
curl -X POST http://localhost:8000/ingest/repos/sync-all
```

---

## Supported Languages

Python, JavaScript, TypeScript, Go, Rust, Java, C, C++, Ruby, Kotlin, Swift, Scala,
plus Shell scripts, YAML, TOML, and Terraform files.

---

## Extending the System Prompt

Edit `app/services/prompt_builder.py` to customize AI behavior:

```python
prompt_parts += [
    "## Behavior guidelines",
    "- Cite the repo and file path when referencing code",
    "- Prefer internal patterns over generic solutions",
    "- Flag any security anti-patterns you notice",
    "- Never suggest rewriting existing code unless explicitly asked",
    "- When generating new code, match the style of the retrieved examples",
]
```

---

## Qdrant Dashboard

Browse your vector collections visually at:
```
http://localhost:6333/dashboard
```

## API Docs (auto-generated)

```
http://localhost:8000/docs
```

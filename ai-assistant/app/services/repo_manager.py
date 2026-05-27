import os
import subprocess
import yaml
import redis
import json
from pathlib import Path
from git import Repo, InvalidGitRepositoryError
from app.core.config import settings
from app.services.code_ingest import ingest_repo_directory

COMMIT_KEY_PREFIX = "repo_commit:"


def get_redis():
    return redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        decode_responses=True,
    )


def load_repos_config() -> dict:
    with open(settings.repos_config) as f:
        return yaml.safe_load(f)


def get_last_indexed_commit(repo_name: str) -> str | None:
    r = get_redis()
    return r.get(f"{COMMIT_KEY_PREFIX}{repo_name}")


def save_indexed_commit(repo_name: str, commit_hash: str):
    get_redis().set(f"{COMMIT_KEY_PREFIX}{repo_name}", commit_hash)


def get_current_commit(repo_path: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path,
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def get_changed_files(repo_path: str, from_commit: str, to_commit: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", from_commit, to_commit],
        cwd=repo_path,
        capture_output=True, text=True,
    )
    return [f for f in result.stdout.splitlines() if f]


def clone_or_pull_repo(repo_cfg: dict) -> str:
    """Clone a remote repo or pull latest. Returns local path."""
    name = repo_cfg["name"]
    url = repo_cfg["url"]
    branch = repo_cfg.get("branch", "main")
    token_env = repo_cfg.get("token_env")

    if token_env:
        token = os.getenv(token_env, "")
        # Inject token into URL for HTTPS auth
        if "https://" in url:
            url = url.replace("https://", f"https://oauth2:{token}@")

    local_path = os.path.join(settings.repos_cache, name)

    if os.path.exists(local_path):
        print(f"[git] Pulling latest for {name}...")
        repo = Repo(local_path)
        repo.remotes.origin.pull(branch)
    else:
        print(f"[git] Cloning {name}...")
        os.makedirs(local_path, exist_ok=True)
        Repo.clone_from(url, local_path, branch=branch)

    return local_path


def sync_repo(repo_cfg: dict, global_cfg: dict) -> dict:
    name = repo_cfg["name"]
    exclude = global_cfg.get("exclude", [])
    chunk_size = repo_cfg.get("chunk_size", global_cfg.get("chunk_size", 400))
    chunk_overlap = repo_cfg.get("chunk_overlap", global_cfg.get("chunk_overlap", 60))

    print(f"\n[sync] Starting sync for repo: {name}")

    try:
        # Resolve local path
        if repo_cfg["type"] == "remote":
            repo_path = clone_or_pull_repo(repo_cfg)
        else:
            repo_path = repo_cfg["path"]

        if not os.path.exists(repo_path):
            return {"repo": name, "status": "error", "error": f"Path not found: {repo_path}"}

        current_commit = get_current_commit(repo_path)
        last_commit = get_last_indexed_commit(name)

        if last_commit == current_commit:
            print(f"[sync] {name} is up to date at {current_commit[:8]}")
            return {"repo": name, "status": "up_to_date", "commit": current_commit[:8]}

        if last_commit:
            print(f"[sync] {name} — incremental from {last_commit[:8]} → {current_commit[:8]}")
            changed = get_changed_files(repo_path, last_commit, current_commit)
            results = ingest_repo_directory(
                repo_path, name, exclude, chunk_size, chunk_overlap, changed_files=changed
            )
        else:
            print(f"[sync] {name} — full initial ingest")
            results = ingest_repo_directory(
                repo_path, name, exclude, chunk_size, chunk_overlap, changed_files=None
            )

        save_indexed_commit(name, current_commit)
        return {
            "repo": name,
            "status": "synced",
            "commit": current_commit[:8],
            **results,
        }

    except Exception as e:
        print(f"[sync] ERROR syncing {name}: {e}")
        return {"repo": name, "status": "error", "error": str(e)}


def sync_all_repos() -> list[dict]:
    config = load_repos_config()
    global_cfg = config.get("global", {})
    repos = config.get("repos", [])
    results = []
    for repo_cfg in repos:
        result = sync_repo(repo_cfg, global_cfg)
        results.append(result)
        print(f"[sync] {repo_cfg['name']}: {result}")
    return results

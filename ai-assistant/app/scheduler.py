"""
scheduler.py — runs as a separate container.
Polls repos on the interval defined in repos.yml / SYNC_INTERVAL_MINUTES.
"""
import time
import yaml
from apscheduler.schedulers.blocking import BlockingScheduler
from app.services.repo_manager import sync_repo, load_repos_config
from app.core.config import settings


def sync_job():
    print("\n[scheduler] Running scheduled repo sync...")
    config = load_repos_config()
    global_cfg = config.get("global", {})
    for repo_cfg in config.get("repos", []):
        sync_repo(repo_cfg, global_cfg)
    print("[scheduler] Sync complete.")


def main():
    config = load_repos_config()
    global_cfg = config.get("global", {})
    interval = global_cfg.get("sync_interval_minutes", settings.sync_interval_minutes)

    print(f"[scheduler] Starting — sync interval: {interval} minutes")

    # Run once immediately on startup
    sync_job()

    scheduler = BlockingScheduler()
    scheduler.add_job(sync_job, "interval", minutes=interval, id="repo_sync")
    scheduler.start()


if __name__ == "__main__":
    main()

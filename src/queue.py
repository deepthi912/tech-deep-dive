"""URL queue: manages user-submitted blog/doc/video URLs for podcast generation."""

import logging
from datetime import datetime

from .utils import get_data_dir, load_json, save_json

logger = logging.getLogger(__name__)

QUEUE_FILE = "url_queue.json"


def _queue_path():
    return get_data_dir() / QUEUE_FILE


def add_urls(urls: list[str]) -> list[dict]:
    """Add URLs to the queue. Returns list of added entries."""
    queue = load_json(_queue_path(), default={"videos": []})
    existing = {v["url"] for v in queue["videos"]}
    added = []

    for url in urls:
        url = url.strip()
        if not url or url in existing:
            continue
        entry = {
            "url": url,
            "title": "",
            "added_at": datetime.now().isoformat(),
            "status": "pending",
        }
        queue["videos"].append(entry)
        existing.add(url)
        added.append(entry)

    save_json(_queue_path(), queue)
    logger.info(f"Added {len(added)} URLs to queue")
    return added


def get_pending_urls() -> list[str]:
    queue = load_json(_queue_path(), default={"videos": []})
    return [v["url"] for v in queue["videos"] if v["status"] == "pending"]


def get_all_queue() -> list[dict]:
    queue = load_json(_queue_path(), default={"videos": []})
    return queue.get("videos", [])


def mark_urls_used(urls: list[str]):
    queue = load_json(_queue_path(), default={"videos": []})
    used_set = set(urls)
    for v in queue["videos"]:
        if v["url"] in used_set:
            v["status"] = "used"
    save_json(_queue_path(), queue)


def update_title(url: str, title: str):
    queue = load_json(_queue_path(), default={"videos": []})
    for v in queue["videos"]:
        if v["url"] == url:
            v["title"] = title
            break
    save_json(_queue_path(), queue)


def remove_url(url: str):
    queue = load_json(_queue_path(), default={"videos": []})
    queue["videos"] = [v for v in queue["videos"] if v["url"] != url]
    save_json(_queue_path(), queue)

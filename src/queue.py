"""URL queue: manages user-submitted YouTube video URLs for podcast generation."""

import logging
import re
from dataclasses import dataclass
from datetime import datetime

from .utils import get_data_dir, load_json, save_json

logger = logging.getLogger(__name__)

QUEUE_FILE = "url_queue.json"


@dataclass
class QueuedVideo:
    url: str
    video_id: str
    title: str
    added_at: str
    status: str  # pending, used, failed


def _queue_path():
    return get_data_dir() / QUEUE_FILE


def _extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r"(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",
    ]
    for pat in patterns:
        match = re.search(pat, url.strip())
        if match:
            return match.group(1)
    return None


def add_urls(urls: list[str]) -> list[dict]:
    """Add YouTube URLs to the queue. Returns list of added entries."""
    queue = load_json(_queue_path(), default={"videos": []})
    existing_ids = {v["video_id"] for v in queue["videos"]}
    added = []

    for url in urls:
        url = url.strip()
        if not url:
            continue
        video_id = _extract_video_id(url)
        if not video_id:
            logger.warning(f"Could not extract video ID from: {url}")
            continue
        if video_id in existing_ids:
            logger.info(f"Already in queue: {video_id}")
            continue

        entry = {
            "url": url,
            "video_id": video_id,
            "title": "",
            "added_at": datetime.now().isoformat(),
            "status": "pending",
        }
        queue["videos"].append(entry)
        existing_ids.add(video_id)
        added.append(entry)

    save_json(_queue_path(), queue)
    logger.info(f"Added {len(added)} URLs to queue")
    return added


def get_pending_videos() -> list[dict]:
    """Get all pending (unused) videos from the queue."""
    queue = load_json(_queue_path(), default={"videos": []})
    return [v for v in queue["videos"] if v["status"] == "pending"]


def get_all_queue() -> list[dict]:
    """Get the entire queue."""
    queue = load_json(_queue_path(), default={"videos": []})
    return queue.get("videos", [])


def mark_videos_used(video_ids: list[str]):
    """Mark videos as used after generating an episode."""
    queue = load_json(_queue_path(), default={"videos": []})
    for v in queue["videos"]:
        if v["video_id"] in video_ids:
            v["status"] = "used"
    save_json(_queue_path(), queue)


def remove_video(video_id: str):
    """Remove a video from the queue."""
    queue = load_json(_queue_path(), default={"videos": []})
    queue["videos"] = [v for v in queue["videos"] if v["video_id"] != video_id]
    save_json(_queue_path(), queue)

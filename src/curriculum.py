"""Curriculum engine: tracks which technology to cover today and manages progress."""

import logging
from datetime import date, datetime
from pathlib import Path

from .utils import get_data_dir, load_curriculum, load_json, save_json

logger = logging.getLogger(__name__)

PROGRESS_FILE = "progress.json"


def _progress_path() -> Path:
    return get_data_dir() / PROGRESS_FILE


def load_progress() -> dict:
    return load_json(_progress_path(), default={"completed": [], "current_index": 0})


def save_progress(progress: dict):
    save_json(_progress_path(), progress)


def get_todays_topic(override_topic: str | None = None, override_day: int | None = None) -> dict:
    """
    Determine today's technology topic.

    Args:
        override_topic: Force a specific technology name (e.g., "Apache Spark")
        override_day: Jump to a specific day number in the curriculum (1-indexed)

    Returns:
        dict with keys: name, category, searches, day_number
    """
    curriculum = load_curriculum()

    if not curriculum:
        raise ValueError("Curriculum is empty. Check curriculum.yaml")

    if override_topic:
        for i, tech in enumerate(curriculum):
            if tech["name"].lower() == override_topic.lower():
                logger.info(f"Topic override: {tech['name']}")
                return {**tech, "day_number": i + 1}
        available = [t["name"] for t in curriculum]
        raise ValueError(
            f"Topic '{override_topic}' not found in curriculum. "
            f"Available: {', '.join(available)}"
        )

    if override_day is not None:
        idx = (override_day - 1) % len(curriculum)
        tech = curriculum[idx]
        logger.info(f"Day override: day {override_day} -> {tech['name']}")
        return {**tech, "day_number": override_day}

    progress = load_progress()
    idx = progress.get("current_index", 0) % len(curriculum)
    tech = curriculum[idx]
    logger.info(f"Today's topic (day {idx + 1}/{len(curriculum)}): {tech['name']}")
    return {**tech, "day_number": idx + 1}


def mark_topic_completed(topic_name: str):
    """Mark a topic as completed and advance the curriculum index."""
    progress = load_progress()
    completed_entry = {
        "name": topic_name,
        "date": date.today().isoformat(),
        "timestamp": datetime.now().isoformat(),
    }
    progress.setdefault("completed", []).append(completed_entry)
    progress["current_index"] = progress.get("current_index", 0) + 1
    save_progress(progress)
    logger.info(f"Marked '{topic_name}' as completed. Next index: {progress['current_index']}")


def get_schedule(count: int = 10) -> list[dict]:
    """Preview the upcoming curriculum schedule."""
    curriculum = load_curriculum()
    progress = load_progress()
    start_idx = progress.get("current_index", 0)

    schedule = []
    for i in range(count):
        idx = (start_idx + i) % len(curriculum)
        tech = curriculum[idx]
        schedule.append({
            "day": start_idx + i + 1,
            "name": tech["name"],
            "category": tech["category"],
            "is_today": i == 0,
        })
    return schedule

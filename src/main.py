"""Main orchestrator: runs the full podcast generation pipeline."""

import argparse
import logging
import shutil
import tempfile
from datetime import date
from pathlib import Path

from .utils import get_data_dir, get_output_dir, load_config, load_json, save_json

logger = logging.getLogger(__name__)

EPISODE_LOG = "episode_log.json"


def _setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _log_episode(episode_meta: dict):
    log_path = get_data_dir() / EPISODE_LOG
    log = load_json(log_path, default={"episodes": []})
    log["episodes"].append(episode_meta)
    save_json(log_path, log)


def get_episode_for_today() -> dict | None:
    """Check if an episode has already been generated today."""
    log_path = get_data_dir() / EPISODE_LOG
    log = load_json(log_path, default={"episodes": []})
    today = date.today().isoformat()
    for ep in log["episodes"]:
        if ep.get("date") == today:
            return ep
    return None


def generate_episode(
    override_topic: str | None = None,
    override_day: int | None = None,
    audio_only: bool = False,
) -> dict:
    """
    Generate a complete podcast episode.
    Returns episode metadata dict.
    """
    from .audio_generator import generate_audio
    from .curriculum import get_schedule, get_todays_topic, mark_topic_completed
    from .discovery import discover_content
    from .podcast_assembler import assemble_podcast
    from .script_writer import generate_script
    from .summarizer import summarize_all
    from .transcriber import transcribe_videos

    config = load_config()

    # 1. Pick today's topic
    topic = get_todays_topic(
        override_topic=override_topic,
        override_day=override_day,
    )
    logger.info(f"{'='*60}")
    logger.info(f"GENERATING EPISODE: Day {topic['day_number']} - {topic['name']}")
    logger.info(f"Category: {topic['category']}")
    logger.info(f"{'='*60}")

    # Figure out next topic for the outro
    schedule = get_schedule(count=2)
    next_topic_name = schedule[1]["name"] if len(schedule) > 1 else "another exciting technology"

    # 2. Discover YouTube content
    logger.info("Step 1/5: Discovering YouTube content...")
    videos = discover_content(topic, config)
    if not videos:
        raise RuntimeError(f"No videos found for {topic['name']}. Check API key and network.")

    # 3. Extract transcripts
    logger.info("Step 2/5: Extracting transcripts...")
    transcribed = transcribe_videos(videos)
    if not transcribed:
        raise RuntimeError(f"Could not extract any transcripts for {topic['name']}")

    # 4. Summarize with Gemini
    logger.info("Step 3/5: Summarizing with AI...")
    summaries = summarize_all(transcribed, topic["name"])
    if not summaries:
        raise RuntimeError(f"Could not generate any summaries for {topic['name']}")

    # 5. Generate podcast script
    logger.info("Step 4/5: Writing podcast script...")
    script = generate_script(
        summaries=summaries,
        technology=topic["name"],
        category=topic["category"],
        next_topic=next_topic_name,
    )

    # 6. Generate audio and assemble
    logger.info("Step 5/5: Generating audio...")
    work_dir = Path(tempfile.mkdtemp(prefix="podcast_"))
    try:
        audio_paths = generate_audio(script.segments, work_dir, config)
        output_path = assemble_podcast(
            audio_paths=audio_paths,
            technology=topic["name"],
            day_number=topic["day_number"],
            config=config,
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    # 7. Mark complete and log
    mark_topic_completed(topic["name"])

    episode_meta = {
        "date": date.today().isoformat(),
        "day_number": topic["day_number"],
        "technology": topic["name"],
        "category": topic["category"],
        "file": str(output_path),
        "filename": output_path.name,
        "total_words": script.total_words,
        "videos_used": len(summaries),
        "segments": [s.name for s in script.segments],
    }
    _log_episode(episode_meta)

    logger.info(f"{'='*60}")
    logger.info(f"EPISODE COMPLETE: {output_path.name}")
    logger.info(f"Words: {script.total_words}, Videos sourced: {len(summaries)}")
    logger.info(f"{'='*60}")

    return episode_meta


def get_all_episodes() -> list[dict]:
    """Return all generated episodes from the log."""
    log_path = get_data_dir() / EPISODE_LOG
    log = load_json(log_path, default={"episodes": []})
    return log.get("episodes", [])


def main():
    _setup_logging()

    parser = argparse.ArgumentParser(description="Tech Deep Dive Podcast Generator")
    parser.add_argument("--topic", type=str, help="Override: specific technology name")
    parser.add_argument("--day", type=int, help="Override: jump to curriculum day N")
    parser.add_argument("--schedule", action="store_true", help="Show upcoming schedule")
    parser.add_argument("--audio-only", action="store_true", help="Regenerate audio only")
    args = parser.parse_args()

    if args.schedule:
        from .curriculum import get_schedule
        schedule = get_schedule(count=15)
        print("\nUpcoming Tech Deep Dive Schedule:")
        print("-" * 50)
        for item in schedule:
            marker = " <-- TODAY" if item["is_today"] else ""
            print(f"  Day {item['day']:3d}: {item['name']:<25s} [{item['category']}]{marker}")
        print()
        return

    from dotenv import load_dotenv
    load_dotenv()

    generate_episode(
        override_topic=args.topic,
        override_day=args.day,
        audio_only=args.audio_only,
    )


if __name__ == "__main__":
    main()

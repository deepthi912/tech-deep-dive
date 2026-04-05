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
    log_path = get_data_dir() / EPISODE_LOG
    log = load_json(log_path, default={"episodes": []})
    today = date.today().isoformat()
    for ep in log["episodes"]:
        if ep.get("date") == today:
            return ep
    return None


def generate_from_urls(
    video_urls: list[str] | None = None,
    episode_title: str = "Custom Episode",
) -> dict:
    """
    Generate a podcast episode from specific YouTube URLs.
    Uses only 2 Gemini API calls total (1 summary + 1 script).
    """
    from .audio_generator import generate_audio
    from .discovery import VideoInfo
    from .podcast_assembler import assemble_podcast
    from .queue import get_pending_videos, mark_videos_used
    from .script_writer import generate_script
    from .summarizer import summarize_all
    from .transcriber import TranscribedVideo, extract_transcript

    config = load_config()

    # Get videos from queue if no URLs provided
    if not video_urls:
        pending = get_pending_videos()
        if not pending:
            raise RuntimeError("No videos in queue. Add YouTube URLs first.")
        video_urls = [v["url"] for v in pending]

    logger.info(f"{'='*60}")
    logger.info(f"GENERATING FROM {len(video_urls)} URLs: {episode_title}")
    logger.info(f"{'='*60}")

    # 1. Create VideoInfo objects directly (no YouTube API search needed)
    import re
    videos = []
    for url in video_urls:
        match = re.search(r"(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})", url)
        if match:
            vid = match.group(1)
            videos.append(VideoInfo(
                video_id=vid,
                title="",
                channel="",
                description="",
                view_count=0,
                duration_label="",
                url=url,
            ))

    if not videos:
        raise RuntimeError("No valid YouTube URLs provided")

    # 2. Extract transcripts (no API key needed -- free)
    logger.info(f"Step 1/4: Extracting transcripts from {len(videos)} videos...")
    transcribed = []
    for video in videos:
        result = extract_transcript(video)
        if result.transcript and len(result.transcript) > 50:
            transcribed.append(result)

    if not transcribed:
        raise RuntimeError("Could not extract transcripts from any videos")
    logger.info(f"Got transcripts for {len(transcribed)}/{len(videos)} videos")

    # 3. Summarize ALL in one Gemini call
    logger.info("Step 2/4: Summarizing with AI (1 API call)...")
    summaries = summarize_all(transcribed, episode_title)

    # 4. Generate script (1 Gemini call)
    logger.info("Step 3/4: Writing podcast script (1 API call)...")
    script = generate_script(
        summaries=summaries,
        technology=episode_title,
        category="Technology",
        next_topic="the next topic you add",
    )

    # 5. Generate audio and assemble
    logger.info("Step 4/4: Generating audio...")
    work_dir = Path(tempfile.mkdtemp(prefix="podcast_"))
    try:
        audio_paths = generate_audio(script.segments, work_dir, config)

        log_path = get_data_dir() / EPISODE_LOG
        log = load_json(log_path, default={"episodes": []})
        day_number = len(log.get("episodes", [])) + 1

        output_path = assemble_podcast(
            audio_paths=audio_paths,
            technology=episode_title,
            day_number=day_number,
            config=config,
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    # Mark queued videos as used
    used_ids = [v.video_id for v in videos]
    mark_videos_used(used_ids)

    episode_meta = {
        "date": date.today().isoformat(),
        "day_number": day_number,
        "technology": episode_title,
        "category": "Custom",
        "file": str(output_path),
        "filename": output_path.name,
        "total_words": script.total_words,
        "videos_used": len(summaries),
        "segments": [s.name for s in script.segments],
        "source_urls": [v.url for v in videos],
    }
    _log_episode(episode_meta)

    logger.info(f"{'='*60}")
    logger.info(f"EPISODE COMPLETE: {output_path.name}")
    logger.info(f"Words: {script.total_words}, Videos sourced: {len(summaries)}")
    logger.info(f"Gemini API calls used: 2")
    logger.info(f"{'='*60}")

    return episode_meta


def generate_episode(
    override_topic: str | None = None,
    override_day: int | None = None,
    audio_only: bool = False,
) -> dict:
    """Generate episode from curriculum + channel discovery."""
    from .audio_generator import generate_audio
    from .curriculum import get_schedule, get_todays_topic, mark_topic_completed
    from .discovery import discover_content
    from .podcast_assembler import assemble_podcast
    from .script_writer import generate_script
    from .summarizer import summarize_all
    from .transcriber import transcribe_videos

    config = load_config()

    topic = get_todays_topic(
        override_topic=override_topic,
        override_day=override_day,
    )
    logger.info(f"{'='*60}")
    logger.info(f"GENERATING EPISODE: Day {topic['day_number']} - {topic['name']}")
    logger.info(f"{'='*60}")

    schedule = get_schedule(count=2)
    next_topic_name = schedule[1]["name"] if len(schedule) > 1 else "another exciting technology"

    logger.info("Step 1/4: Discovering YouTube content...")
    videos = discover_content(topic, config)
    if not videos:
        raise RuntimeError(f"No videos found for {topic['name']}")

    logger.info("Step 2/4: Extracting transcripts...")
    transcribed = transcribe_videos(videos)
    if not transcribed:
        raise RuntimeError(f"Could not extract transcripts for {topic['name']}")

    logger.info("Step 3/4: Summarizing + writing script (2 API calls)...")
    summaries = summarize_all(transcribed, topic["name"])
    if not summaries:
        raise RuntimeError(f"Summarization failed for {topic['name']}")

    script = generate_script(
        summaries=summaries,
        technology=topic["name"],
        category=topic["category"],
        next_topic=next_topic_name,
    )

    logger.info("Step 4/4: Generating audio...")
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

    logger.info(f"EPISODE COMPLETE: {output_path.name}")
    return episode_meta


def get_all_episodes() -> list[dict]:
    log_path = get_data_dir() / EPISODE_LOG
    log = load_json(log_path, default={"episodes": []})
    return log.get("episodes", [])


def main():
    _setup_logging()
    parser = argparse.ArgumentParser(description="Tech Deep Dive Podcast Generator")
    parser.add_argument("--topic", type=str, help="Override: specific technology name")
    parser.add_argument("--day", type=int, help="Override: jump to curriculum day N")
    parser.add_argument("--schedule", action="store_true", help="Show upcoming schedule")
    args = parser.parse_args()

    if args.schedule:
        from .curriculum import get_schedule
        schedule = get_schedule(count=15)
        print("\nUpcoming Tech Deep Dive Schedule:")
        print("-" * 50)
        for item in schedule:
            marker = " <-- TODAY" if item["is_today"] else ""
            print(f"  Day {item['day']:3d}: {item['name']:<25s} [{item['category']}]{marker}")
        return

    from dotenv import load_dotenv
    load_dotenv()

    generate_episode(override_topic=args.topic, override_day=args.day)


if __name__ == "__main__":
    main()

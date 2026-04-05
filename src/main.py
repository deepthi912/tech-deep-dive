"""Main orchestrator: runs the full podcast generation pipeline.

Flow: Scrape URLs -> Summarize (1 Gemini call) -> Script (1 Gemini call) -> Audio -> Podcast
Total API calls: 2 per episode.
"""

import logging
import shutil
import tempfile
from datetime import date
from pathlib import Path

from .utils import get_data_dir, get_output_dir, load_config, load_json, save_json

logger = logging.getLogger(__name__)

EPISODE_LOG = "episode_log.json"


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
    urls: list[str] | None = None,
    episode_title: str = "Tech Deep Dive Episode",
) -> dict:
    """
    Generate a podcast episode from blog/doc URLs.
    Uses only 2 Gemini API calls (1 summary + 1 script).
    """
    from .audio_generator import generate_audio
    from .podcast_assembler import assemble_podcast
    from .queue import get_pending_urls, mark_urls_used, update_title
    from .script_writer import generate_script
    from .summarizer import summarize_pages

    config = load_config()

    if not urls:
        urls = get_pending_urls()
        if not urls:
            raise RuntimeError("No URLs in queue. Add blog/doc URLs first.")

    logger.info(f"{'='*60}")
    logger.info(f"GENERATING: {episode_title}")
    logger.info(f"Sources: {len(urls)} URLs")
    logger.info(f"{'='*60}")

    # 1. Scrape web pages (free, no API needed)
    logger.info("Step 1/4: Scraping web pages...")
    from .scraper import scrape_url
    all_results = [scrape_url(u, i) for i, u in enumerate(urls)]
    pages = [p for p in all_results if p.success]
    failed = [p for p in all_results if not p.success]

    if not pages:
        error_details = "; ".join(f"{p.url} -> {p.error}" for p in failed)
        raise RuntimeError(
            f"Could not extract content from any of the {len(urls)} URLs. "
            f"Errors: {error_details}"
        )
    if failed:
        logger.warning(f"{len(failed)} URLs failed, continuing with {len(pages)}")
    logger.info(f"Scraped {len(pages)}/{len(urls)} pages")

    for page in pages:
        update_title(page.url, page.title)

    # 2. Summarize ALL in one Gemini call
    logger.info("Step 2/4: Summarizing with AI (1 API call)...")
    summaries = summarize_pages(pages, episode_title)

    # 3. Generate script (1 Gemini call)
    logger.info("Step 3/4: Writing podcast script (1 API call)...")
    script = generate_script(
        summaries=summaries,
        technology=episode_title,
        category="Technology",
        next_topic="the next topic you add",
    )

    # 4. Generate audio and assemble
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

    mark_urls_used(urls)

    # Build per-article summaries for the UI
    article_summaries = []
    for s in summaries:
        article_summaries.append({
            "title": s.title,
            "url": s.url,
            "domain": s.domain,
            "summary": s.summary,
            "key_points": s.key_points,
            "architecture_details": s.architecture_details,
            "use_cases": s.use_cases,
        })

    episode_meta = {
        "date": date.today().isoformat(),
        "day_number": day_number,
        "technology": episode_title,
        "category": "Custom",
        "file": str(output_path),
        "filename": output_path.name,
        "total_words": script.total_words,
        "sources_used": len(summaries),
        "segments": [s.name for s in script.segments],
        "source_urls": urls,
        "summaries": article_summaries,
    }
    _log_episode(episode_meta)

    logger.info(f"{'='*60}")
    logger.info(f"EPISODE COMPLETE: {output_path.name}")
    logger.info(f"Words: {script.total_words}, Sources: {len(summaries)}")
    logger.info(f"Gemini API calls used: 2")
    logger.info(f"{'='*60}")

    return episode_meta


def get_all_episodes() -> list[dict]:
    log_path = get_data_dir() / EPISODE_LOG
    log = load_json(log_path, default={"episodes": []})
    return log.get("episodes", [])

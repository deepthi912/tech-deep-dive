"""YouTube content discovery: finds the best videos for a given technology topic."""

import logging
import os
from dataclasses import dataclass

from googleapiclient.discovery import build

logger = logging.getLogger(__name__)


@dataclass
class VideoInfo:
    video_id: str
    title: str
    channel: str
    description: str
    view_count: int
    duration_label: str
    url: str


def _get_youtube_client():
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        raise ValueError("YOUTUBE_API_KEY environment variable not set")
    return build("youtube", "v3", developerKey=api_key)


def _parse_duration_to_minutes(duration: str) -> int:
    """Parse ISO 8601 duration (PT1H2M3S) to minutes."""
    import re
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    return hours * 60 + minutes


def search_videos(
    searches: list[str],
    max_results_per_query: int = 10,
    min_duration_minutes: int = 5,
) -> list[VideoInfo]:
    """
    Search YouTube for videos matching the given queries.
    Returns deduplicated, ranked videos sorted by relevance and views.
    """
    youtube = _get_youtube_client()
    seen_ids: set[str] = set()
    candidates: list[VideoInfo] = []

    for query in searches:
        logger.info(f"Searching YouTube: '{query}'")
        try:
            search_resp = youtube.search().list(
                q=query,
                part="snippet",
                type="video",
                maxResults=max_results_per_query,
                order="relevance",
                videoCaption="closedCaption",
                relevanceLanguage="en",
            ).execute()
        except Exception as e:
            logger.warning(f"Search failed for '{query}': {e}")
            continue

        video_ids = []
        snippet_map = {}
        for item in search_resp.get("items", []):
            vid = item["id"]["videoId"]
            if vid not in seen_ids:
                video_ids.append(vid)
                snippet_map[vid] = item["snippet"]
                seen_ids.add(vid)

        if not video_ids:
            continue

        details_resp = youtube.videos().list(
            part="contentDetails,statistics",
            id=",".join(video_ids),
        ).execute()

        for detail in details_resp.get("items", []):
            vid = detail["id"]
            duration_min = _parse_duration_to_minutes(
                detail["contentDetails"]["duration"]
            )
            if duration_min < min_duration_minutes:
                continue

            snippet = snippet_map.get(vid, {})
            view_count = int(detail.get("statistics", {}).get("viewCount", 0))

            candidates.append(VideoInfo(
                video_id=vid,
                title=snippet.get("title", ""),
                channel=snippet.get("channelTitle", ""),
                description=snippet.get("description", ""),
                view_count=view_count,
                duration_label=detail["contentDetails"]["duration"],
                url=f"https://www.youtube.com/watch?v={vid}",
            ))

    candidates.sort(key=lambda v: v.view_count, reverse=True)
    selected = candidates[:12]
    logger.info(f"Found {len(candidates)} candidates, selected top {len(selected)}")
    return selected


def discover_content(topic: dict, config: dict) -> list[VideoInfo]:
    """Main entry point: discover YouTube content for a curriculum topic."""
    yt_config = config.get("youtube", {})
    return search_videos(
        searches=topic["searches"],
        max_results_per_query=yt_config.get("max_results_per_query", 10),
        min_duration_minutes=yt_config.get("min_duration_minutes", 5),
    )

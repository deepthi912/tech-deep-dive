"""YouTube content discovery: fetches videos from curated channels and playlists.

Instead of searching all of YouTube, this module pulls content from specific
channels and playlists that the user has configured as trusted sources.

Quota budget per episode: ~200-400 units (well within free 10,000/day).
"""

import logging
import os
import re
from dataclasses import dataclass

from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

DAILY_QUOTA_LIMIT = 10_000
SAFETY_QUOTA_CAP = 1_000


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
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    return hours * 60 + minutes


def _resolve_channel_id(youtube, handle: str) -> str | None:
    """Resolve a @handle or channel URL to a channel ID."""
    handle = handle.strip().rstrip("/")

    if handle.startswith("UC") and len(handle) == 24:
        return handle

    if "youtube.com/" in handle:
        match = re.search(r"youtube\.com/(?:@|channel/)([^/?&]+)", handle)
        if match:
            handle = match.group(1)
            if handle.startswith("UC") and len(handle) == 24:
                return handle
            if not handle.startswith("@"):
                handle = f"@{handle}"

    if handle.startswith("@"):
        handle = handle[1:]

    try:
        resp = youtube.channels().list(
            part="id",
            forHandle=handle,
        ).execute()
        items = resp.get("items", [])
        if items:
            return items[0]["id"]
    except Exception as e:
        logger.warning(f"Could not resolve handle '{handle}': {e}")

    try:
        resp = youtube.search().list(
            q=handle,
            part="snippet",
            type="channel",
            maxResults=1,
        ).execute()
        items = resp.get("items", [])
        if items:
            return items[0]["snippet"]["channelId"]
    except Exception as e:
        logger.warning(f"Channel search failed for '{handle}': {e}")

    return None


def _fetch_playlist_videos(youtube, playlist_id: str, max_items: int = 20) -> list[dict]:
    """Fetch video IDs and snippets from a playlist. Costs 1 quota unit per call."""
    videos = []
    try:
        resp = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=playlist_id,
            maxResults=min(max_items, 50),
        ).execute()
        for item in resp.get("items", []):
            videos.append({
                "video_id": item["contentDetails"]["videoId"],
                "title": item["snippet"].get("title", ""),
                "channel": item["snippet"].get("videoOwnerChannelTitle", ""),
                "description": item["snippet"].get("description", ""),
            })
    except Exception as e:
        logger.warning(f"Failed to fetch playlist {playlist_id}: {e}")
    return videos


def _fetch_channel_videos(
    youtube, channel_id: str, topic: str, max_results: int = 10
) -> list[dict]:
    """Search for topic-relevant videos within a specific channel. Costs 100 units."""
    videos = []
    try:
        resp = youtube.search().list(
            q=topic,
            part="snippet",
            type="video",
            channelId=channel_id,
            maxResults=max_results,
            order="relevance",
            videoCaption="closedCaption",
        ).execute()
        for item in resp.get("items", []):
            videos.append({
                "video_id": item["id"]["videoId"],
                "title": item["snippet"].get("title", ""),
                "channel": item["snippet"].get("channelTitle", ""),
                "description": item["snippet"].get("description", ""),
            })
    except Exception as e:
        logger.warning(f"Channel search failed for {channel_id}: {e}")
    return videos


def _enrich_with_details(
    youtube, raw_videos: list[dict], min_duration_minutes: int = 3
) -> list[VideoInfo]:
    """Fetch duration and view counts for a batch of videos. Costs ~3 units per call."""
    if not raw_videos:
        return []

    seen = set()
    unique = []
    for v in raw_videos:
        if v["video_id"] not in seen:
            seen.add(v["video_id"])
            unique.append(v)

    results = []
    for i in range(0, len(unique), 50):
        batch = unique[i:i + 50]
        ids = ",".join(v["video_id"] for v in batch)
        try:
            resp = youtube.videos().list(
                part="contentDetails,statistics",
                id=ids,
            ).execute()
        except Exception as e:
            logger.warning(f"Video details fetch failed: {e}")
            continue

        detail_map = {item["id"]: item for item in resp.get("items", [])}
        for v in batch:
            detail = detail_map.get(v["video_id"])
            if not detail:
                continue
            duration_min = _parse_duration_to_minutes(
                detail["contentDetails"]["duration"]
            )
            if duration_min < min_duration_minutes:
                continue
            view_count = int(detail.get("statistics", {}).get("viewCount", 0))
            results.append(VideoInfo(
                video_id=v["video_id"],
                title=v["title"],
                channel=v["channel"],
                description=v["description"],
                view_count=view_count,
                duration_label=detail["contentDetails"]["duration"],
                url=f"https://www.youtube.com/watch?v={v['video_id']}",
            ))

    return results


def discover_content(topic: dict, config: dict) -> list[VideoInfo]:
    """
    Discover YouTube content for a topic from configured channels and playlists.
    Searches within specific channels for topic-relevant videos,
    and pulls from curated playlists.
    """
    youtube = _get_youtube_client()
    yt_config = config.get("youtube", {})
    sources = yt_config.get("sources", {})
    channels = sources.get("channels", [])
    playlists = sources.get("playlists", [])
    min_duration = yt_config.get("min_duration_minutes", 3)

    topic_name = topic["name"]
    all_raw: list[dict] = []
    quota_used = 0

    # 1. Search within each configured channel for this topic
    for ch_url in channels:
        if quota_used > SAFETY_QUOTA_CAP:
            logger.info(f"Quota cap reached ({quota_used}), stopping channel searches")
            break

        channel_id = _resolve_channel_id(youtube, ch_url)
        quota_used += 3  # channels.list cost
        if not channel_id:
            continue

        videos = _fetch_channel_videos(youtube, channel_id, topic_name, max_results=8)
        quota_used += 100  # search.list cost
        all_raw.extend(videos)
        logger.info(f"Channel {ch_url}: found {len(videos)} videos for '{topic_name}'")

    # 2. Pull from configured playlists (very cheap: 1 unit each)
    for pl_id in playlists:
        if quota_used > SAFETY_QUOTA_CAP:
            break
        videos = _fetch_playlist_videos(youtube, pl_id, max_items=20)
        quota_used += 1
        # Filter playlist videos to those relevant to the topic
        topic_lower = topic_name.lower()
        topic_words = set(topic_lower.split())
        relevant = [
            v for v in videos
            if _is_relevant(v, topic_words, topic_lower)
        ]
        all_raw.extend(relevant)
        logger.info(
            f"Playlist {pl_id}: {len(relevant)}/{len(videos)} relevant to '{topic_name}'"
        )

    if not all_raw:
        logger.warning(f"No videos found from channels/playlists for '{topic_name}', "
                       "falling back to global search")
        all_raw = _fallback_global_search(youtube, topic, quota_used)

    # 3. Enrich with duration and view counts
    enriched = _enrich_with_details(youtube, all_raw, min_duration)
    enriched.sort(key=lambda v: v.view_count, reverse=True)
    selected = enriched[:12]

    logger.info(
        f"Discovery complete: {len(selected)} videos selected for '{topic_name}'. "
        f"Estimated quota: ~{quota_used} units"
    )
    return selected


def _is_relevant(video: dict, topic_words: set[str], topic_lower: str) -> bool:
    """Check if a video is relevant to the topic based on title/description."""
    text = f"{video.get('title', '')} {video.get('description', '')}".lower()
    if topic_lower in text:
        return True
    matches = sum(1 for w in topic_words if len(w) > 3 and w in text)
    return matches >= len(topic_words) * 0.5


def _fallback_global_search(youtube, topic: dict, quota_used: int) -> list[dict]:
    """If no channel/playlist results, do a limited global search."""
    videos = []
    searches = topic.get("searches", [f"{topic['name']} architecture tutorial"])[:2]
    for query in searches:
        if quota_used > SAFETY_QUOTA_CAP:
            break
        try:
            resp = youtube.search().list(
                q=query,
                part="snippet",
                type="video",
                maxResults=8,
                order="relevance",
                videoCaption="closedCaption",
                relevanceLanguage="en",
            ).execute()
            quota_used += 100
            for item in resp.get("items", []):
                videos.append({
                    "video_id": item["id"]["videoId"],
                    "title": item["snippet"].get("title", ""),
                    "channel": item["snippet"].get("channelTitle", ""),
                    "description": item["snippet"].get("description", ""),
                })
        except Exception as e:
            logger.warning(f"Fallback search failed for '{query}': {e}")
    return videos

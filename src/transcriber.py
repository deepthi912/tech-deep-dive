"""Transcript extraction from YouTube videos using youtube-transcript-api v1.x."""

import logging
from dataclasses import dataclass

from youtube_transcript_api import YouTubeTranscriptApi

from .discovery import VideoInfo

logger = logging.getLogger(__name__)

_ytt = YouTubeTranscriptApi()


@dataclass
class TranscribedVideo:
    video: VideoInfo
    transcript: str
    has_transcript: bool


def _clean_transcript(fetched) -> str:
    """Convert a FetchedTranscript (or raw segments) into clean flowing text."""
    try:
        segments = fetched.to_raw_data()
    except AttributeError:
        segments = fetched
    texts = [seg["text"] for seg in segments]
    full = " ".join(texts)
    full = full.replace("\n", " ")
    while "  " in full:
        full = full.replace("  ", " ")
    return full.strip()


def extract_transcript(video: VideoInfo) -> TranscribedVideo:
    """Extract transcript for a single video. Falls back to description if unavailable."""
    # Try fetching English transcript directly
    try:
        fetched = _ytt.fetch(video.video_id, languages=["en"])
        transcript = _clean_transcript(fetched)
        logger.info(f"Transcript extracted: '{video.title}' ({len(transcript)} chars)")
        return TranscribedVideo(video=video, transcript=transcript, has_transcript=True)
    except Exception:
        pass

    # Try listing available transcripts and picking any English or translated one
    try:
        transcript_list = _ytt.list(video.video_id)
        for t in transcript_list:
            if t.language_code.startswith("en"):
                fetched = t.fetch()
                transcript = _clean_transcript(fetched)
                logger.info(f"Transcript (alt) extracted: '{video.title}'")
                return TranscribedVideo(video=video, transcript=transcript, has_transcript=True)
        # No English found -- try translating the first available
        for t in transcript_list:
            try:
                translated = t.translate("en")
                fetched = translated.fetch()
                transcript = _clean_transcript(fetched)
                logger.info(f"Transcript (translated) extracted: '{video.title}'")
                return TranscribedVideo(video=video, transcript=transcript, has_transcript=True)
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"No transcript for '{video.title}': {e}")

    fallback = f"{video.title}. {video.description}"
    return TranscribedVideo(video=video, transcript=fallback, has_transcript=False)


def transcribe_videos(videos: list[VideoInfo]) -> list[TranscribedVideo]:
    """Extract transcripts for all discovered videos."""
    results = []
    for video in videos:
        result = extract_transcript(video)
        if result.transcript and len(result.transcript) > 50:
            results.append(result)
    logger.info(
        f"Transcribed {len(results)}/{len(videos)} videos "
        f"({sum(1 for r in results if r.has_transcript)} with full transcripts)"
    )
    return results

"""Transcript extraction from YouTube videos using youtube-transcript-api."""

import logging
from dataclasses import dataclass

from youtube_transcript_api import YouTubeTranscriptApi

from .discovery import VideoInfo

logger = logging.getLogger(__name__)


@dataclass
class TranscribedVideo:
    video: VideoInfo
    transcript: str
    has_transcript: bool


def _clean_transcript(raw_segments: list[dict]) -> str:
    """Join transcript segments into clean flowing text."""
    texts = [seg["text"] for seg in raw_segments]
    full = " ".join(texts)
    full = full.replace("\n", " ")
    # Collapse multiple spaces
    while "  " in full:
        full = full.replace("  ", " ")
    return full.strip()


def extract_transcript(video: VideoInfo) -> TranscribedVideo:
    """Extract transcript for a single video. Falls back to description if unavailable."""
    try:
        segments = YouTubeTranscriptApi.get_transcript(
            video.video_id, languages=["en"]
        )
        transcript = _clean_transcript(segments)
        logger.info(f"Transcript extracted: '{video.title}' ({len(transcript)} chars)")
        return TranscribedVideo(video=video, transcript=transcript, has_transcript=True)
    except Exception:
        pass

    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video.video_id)
        for t in transcript_list:
            if t.language_code.startswith("en"):
                segments = t.fetch()
                transcript = _clean_transcript(segments)
                logger.info(f"Transcript (alt) extracted: '{video.title}'")
                return TranscribedVideo(video=video, transcript=transcript, has_transcript=True)
            translated = t.translate("en")
            segments = translated.fetch()
            transcript = _clean_transcript(segments)
            logger.info(f"Transcript (translated) extracted: '{video.title}'")
            return TranscribedVideo(video=video, transcript=transcript, has_transcript=True)
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

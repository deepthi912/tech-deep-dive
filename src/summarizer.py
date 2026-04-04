"""AI summarization of video transcripts using Google Gemini."""

import json
import logging
import os
from dataclasses import dataclass

import google.generativeai as genai

from .transcriber import TranscribedVideo
from .utils import truncate_text

logger = logging.getLogger(__name__)


@dataclass
class VideoSummary:
    title: str
    channel: str
    url: str
    category: str  # basics, architecture, use_case, advanced, comparison
    summary: str
    key_points: list[str]
    architecture_details: str
    use_cases: list[str]


def _get_model():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-1.5-flash")


SUMMARIZE_PROMPT = """You are an expert technical content summarizer. Analyze this transcript from a video about {technology} and extract structured information.

VIDEO TITLE: {title}
CHANNEL: {channel}

TRANSCRIPT:
{transcript}

Respond in valid JSON with these fields:
{{
  "category": "one of: basics, architecture, use_case, advanced, comparison",
  "summary": "A comprehensive 3-5 paragraph summary covering all key information",
  "key_points": ["list of 5-8 key takeaways"],
  "architecture_details": "Any architecture/internals information discussed (empty string if none)",
  "use_cases": ["list of real-world use cases mentioned (empty list if none)"]
}}

Be thorough and technical. Capture architectural details, design decisions, and practical insights. Return ONLY valid JSON."""


def summarize_video(video: TranscribedVideo, technology: str) -> VideoSummary | None:
    """Summarize a single transcribed video using Gemini."""
    model = _get_model()
    transcript = truncate_text(video.transcript, max_chars=28000)

    prompt = SUMMARIZE_PROMPT.format(
        technology=technology,
        title=video.video.title,
        channel=video.video.channel,
        transcript=transcript,
    )

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]

        data = json.loads(text)
        logger.info(f"Summarized: '{video.video.title}' -> {data.get('category', 'unknown')}")
        return VideoSummary(
            title=video.video.title,
            channel=video.video.channel,
            url=video.video.url,
            category=data.get("category", "basics"),
            summary=data.get("summary", ""),
            key_points=data.get("key_points", []),
            architecture_details=data.get("architecture_details", ""),
            use_cases=data.get("use_cases", []),
        )
    except Exception as e:
        logger.error(f"Failed to summarize '{video.video.title}': {e}")
        return None


def summarize_all(
    transcribed: list[TranscribedVideo], technology: str
) -> list[VideoSummary]:
    """Summarize all transcribed videos."""
    summaries = []
    for tv in transcribed:
        summary = summarize_video(tv, technology)
        if summary:
            summaries.append(summary)

    by_cat = {}
    for s in summaries:
        by_cat.setdefault(s.category, []).append(s)
    logger.info(
        f"Summarized {len(summaries)} videos. "
        f"Categories: {', '.join(f'{k}({len(v)})' for k, v in by_cat.items())}"
    )
    return summaries

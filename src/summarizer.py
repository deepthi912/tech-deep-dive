"""AI summarization -- batches ALL transcripts into a single Gemini call.

Gemini free tier allows only 20 requests/day for gemini-2.5-flash.
We use exactly 1 call here + 1 in script_writer = 2 total per episode.
"""

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
    category: str
    summary: str
    key_points: list[str]
    architecture_details: str
    use_cases: list[str]


def _get_model():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-2.5-flash")


BATCH_PROMPT = """You are an expert technical content summarizer. Below are transcripts from multiple videos about {technology}. Analyze ALL of them and return a single JSON array of summaries.

{video_blocks}

Return a JSON array with one object per video. Each object must have:
{{
  "video_index": 0,
  "category": "one of: basics, architecture, use_case, advanced, comparison",
  "summary": "comprehensive 3-5 paragraph summary",
  "key_points": ["5-8 key takeaways"],
  "architecture_details": "architecture/internals info (empty string if none)",
  "use_cases": ["real-world use cases mentioned (empty list if none)"]
}}

Be thorough and technical. Return ONLY a valid JSON array."""


def summarize_all(
    transcribed: list[TranscribedVideo], technology: str
) -> list[VideoSummary]:
    """Summarize ALL transcribed videos in a single Gemini API call."""
    if not transcribed:
        return []

    model = _get_model()

    chars_budget = 90000
    video_blocks = []
    chars_used = 0

    for i, tv in enumerate(transcribed):
        per_video_budget = chars_budget // len(transcribed)
        transcript = truncate_text(tv.transcript, max_chars=per_video_budget)
        block = (
            f"=== VIDEO {i} ===\n"
            f"TITLE: {tv.video.title}\n"
            f"CHANNEL: {tv.video.channel}\n"
            f"TRANSCRIPT:\n{transcript}\n"
        )
        chars_used += len(block)
        if chars_used > chars_budget:
            logger.info(f"Truncating at {i} videos to fit context window")
            break
        video_blocks.append(block)

    prompt = BATCH_PROMPT.format(
        technology=technology,
        video_blocks="\n".join(video_blocks),
    )

    logger.info(
        f"Sending batch summary request: {len(video_blocks)} videos, "
        f"~{len(prompt)} chars (1 Gemini call)"
    )

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                max_output_tokens=16000,
                temperature=0.3,
            ),
        )
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]

        data = json.loads(text)
        if not isinstance(data, list):
            data = [data]

        summaries = []
        for item in data:
            idx = item.get("video_index", len(summaries))
            if idx < len(transcribed):
                tv = transcribed[idx]
            elif summaries:
                continue
            else:
                tv = transcribed[0]

            summaries.append(VideoSummary(
                title=tv.video.title,
                channel=tv.video.channel,
                url=tv.video.url,
                category=item.get("category", "basics"),
                summary=item.get("summary", ""),
                key_points=item.get("key_points", []),
                architecture_details=item.get("architecture_details", ""),
                use_cases=item.get("use_cases", []),
            ))

        logger.info(f"Batch summarized {len(summaries)} videos in 1 API call")
        return summaries

    except Exception as e:
        logger.error(f"Batch summarization failed: {e}")
        raise

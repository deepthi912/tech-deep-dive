"""Podcast script generation: converts summaries into a structured episode script."""

import json
import logging
from dataclasses import dataclass

from .gemini import generate_content
from .summarizer import ArticleSummary

logger = logging.getLogger(__name__)


@dataclass
class PodcastSegment:
    name: str
    text: str
    target_minutes: int


@dataclass
class PodcastScript:
    technology: str
    category: str
    segments: list[PodcastSegment]
    total_words: int


SCRIPT_PROMPT = """You are a professional podcast script writer for "Tech Deep Dive", a daily technology learning podcast. Write a complete, engaging podcast script for today's episode about {technology}.

Here are summaries from blog posts, documentation, and technical articles about {technology}:

{summaries_json}

Write a podcast script (~4500 words total, about 28-32 minutes when spoken). Write every word the narrator should speak -- no stage directions, no brackets, no notes. Just the spoken words.

SEGMENTS:

1. INTRO (target: ~300 words)
- Welcome listeners to Tech Deep Dive
- Introduce today's topic: {technology}
- Brief teaser of what they'll learn

2. FUNDAMENTALS (target: ~1200 words)
- What is {technology} and why it was created
- Core concepts and terminology
- Where it fits in the technology landscape

3. ARCHITECTURE (target: ~1500 words)
- Internal architecture and key components
- How data flows through the system
- Design decisions and trade-offs
- Use vivid mental models: "Imagine a system where..."

4. USE_CASES (target: ~1000 words)
- Real-world production use cases
- Who uses it and why
- When to choose it vs alternatives

5. OUTRO (target: ~500 words)
- Recap the top 5 takeaways
- Sign off

STYLE GUIDELINES:
- Conversational but informative, like explaining to a smart friend
- Use analogies to make complex concepts accessible
- Reference sources naturally: "According to the documentation..." or "As explained in [source]..."
- Avoid filler phrases. Every sentence should teach something.
- Use transitional phrases between ideas
- Make architecture explanations vivid with mental models

Respond with a JSON object:
{{
  "segments": [
    {{"name": "INTRO", "text": "the full spoken text..."}},
    {{"name": "FUNDAMENTALS", "text": "the full spoken text..."}},
    {{"name": "ARCHITECTURE", "text": "the full spoken text..."}},
    {{"name": "USE_CASES", "text": "the full spoken text..."}},
    {{"name": "OUTRO", "text": "the full spoken text..."}}
  ]
}}

Return ONLY valid JSON. Write every word to be spoken aloud."""

SEGMENT_TARGETS = {
    "INTRO": 2,
    "FUNDAMENTALS": 8,
    "ARCHITECTURE": 10,
    "USE_CASES": 7,
    "OUTRO": 3,
}


def _summaries_to_json(summaries: list[ArticleSummary]) -> str:
    data = []
    for s in summaries:
        data.append({
            "title": s.title,
            "source": s.url,
            "summary": s.summary,
            "key_points": s.key_points,
            "architecture_details": s.architecture_details,
            "use_cases": s.use_cases,
        })
    return json.dumps(data, indent=2)


def generate_script(
    summaries: list[ArticleSummary],
    technology: str,
    category: str,
    next_topic: str = "another exciting technology",
) -> PodcastScript:
    """Generate a full podcast episode script from article summaries."""
    summaries_json = _summaries_to_json(summaries)
    prompt = SCRIPT_PROMPT.format(
        technology=technology,
        category=category,
        summaries_json=summaries_json,
        next_topic=next_topic,
    )

    logger.info(f"Generating podcast script for {technology}...")
    text = generate_content(prompt, max_output_tokens=16000, temperature=0.7)
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]

    data = json.loads(text)
    segments = []
    total_words = 0

    for seg_data in data["segments"]:
        name = seg_data["name"]
        seg_text = seg_data["text"]
        word_count = len(seg_text.split())
        total_words += word_count
        segments.append(PodcastSegment(
            name=name,
            text=seg_text,
            target_minutes=SEGMENT_TARGETS.get(name, 5),
        ))

    script = PodcastScript(
        technology=technology,
        category=category,
        segments=segments,
        total_words=total_words,
    )
    est_minutes = total_words / 150
    logger.info(
        f"Script generated: {total_words} words, ~{est_minutes:.0f} min estimated, "
        f"{len(segments)} segments"
    )
    return script

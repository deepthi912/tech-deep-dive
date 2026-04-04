"""Podcast script generation: converts summaries into a structured episode script."""

import json
import logging
import os
from dataclasses import dataclass

import google.generativeai as genai

from .summarizer import VideoSummary

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

Here are summaries from the best conference talks, tutorials, and deep dives about {technology}:

{summaries_json}

Write a COMPLETE podcast script (~9000 words total) divided into these segments. Write every word that the narrator should speak -- no stage directions, no brackets, no notes. Just the spoken words.

SEGMENTS:

1. INTRO (target: ~400 words)
- Welcome listeners to Tech Deep Dive
- Introduce today's technology: {technology}
- Brief teaser of what they'll learn
- Mention this falls under the "{category}" category

2. WHAT_AND_WHY (target: ~1500 words)
- What is {technology}? Explain from the ground up.
- Why was it created? What problem does it solve?
- Brief history and evolution
- Where it fits in the technology landscape

3. ARCHITECTURE (target: ~3000 words)
- Deep dive into internal architecture
- Key components and how they interact
- Data flow and processing model
- Design decisions and trade-offs
- Use diagrams-in-words: "Imagine a system where..."

4. USE_CASES (target: ~2200 words)
- Real-world production use cases
- Who uses it and why? (mention specific companies if referenced)
- Practical applications and scenarios
- When to choose this technology

5. COMPARISONS (target: ~1200 words)
- How {technology} compares to alternatives
- Strengths and weaknesses
- When to use it vs. alternatives

6. OUTRO (target: ~700 words)
- Recap the key takeaways (summarize top 5 things learned)
- Preview tomorrow's topic: {next_topic}
- Sign off

STYLE GUIDELINES:
- Conversational but informative, like explaining to a smart friend
- Use analogies to make complex concepts accessible
- Reference sources naturally: "As discussed in a talk by [channel]..."
- Avoid filler phrases. Every sentence should teach something.
- Use transitional phrases between ideas
- Make architecture explanations vivid with mental models

Respond with a JSON object:
{{
  "segments": [
    {{"name": "INTRO", "text": "the full spoken text..."}},
    {{"name": "WHAT_AND_WHY", "text": "the full spoken text..."}},
    {{"name": "ARCHITECTURE", "text": "the full spoken text..."}},
    {{"name": "USE_CASES", "text": "the full spoken text..."}},
    {{"name": "COMPARISONS", "text": "the full spoken text..."}},
    {{"name": "OUTRO", "text": "the full spoken text..."}}
  ]
}}

Return ONLY valid JSON. Write every word to be spoken aloud."""

SEGMENT_TARGETS = {
    "INTRO": 3,
    "WHAT_AND_WHY": 10,
    "ARCHITECTURE": 20,
    "USE_CASES": 15,
    "COMPARISONS": 7,
    "OUTRO": 5,
}


def _summaries_to_json(summaries: list[VideoSummary]) -> str:
    data = []
    for s in summaries:
        data.append({
            "title": s.title,
            "channel": s.channel,
            "category": s.category,
            "summary": s.summary,
            "key_points": s.key_points,
            "architecture_details": s.architecture_details,
            "use_cases": s.use_cases,
        })
    return json.dumps(data, indent=2)


def generate_script(
    summaries: list[VideoSummary],
    technology: str,
    category: str,
    next_topic: str = "another exciting technology",
) -> PodcastScript:
    """Generate a full podcast episode script from video summaries."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    summaries_json = _summaries_to_json(summaries)
    prompt = SCRIPT_PROMPT.format(
        technology=technology,
        category=category,
        summaries_json=summaries_json,
        next_topic=next_topic,
    )

    logger.info(f"Generating podcast script for {technology}...")
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            max_output_tokens=30000,
            temperature=0.7,
        ),
    )

    text = response.text.strip()
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

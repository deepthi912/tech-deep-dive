"""AI summarization -- batches all scraped content into a single Gemini call.

Uses exactly 1 Gemini call to summarize all articles.
Combined with 1 call in script_writer = 2 total per episode.
"""

import json
import logging
import os
from dataclasses import dataclass

import google.generativeai as genai

from .scraper import ScrapedPage
from .utils import truncate_text

logger = logging.getLogger(__name__)


@dataclass
class ArticleSummary:
    title: str
    url: str
    domain: str
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


BATCH_PROMPT = """You are an expert technical content summarizer. Below are articles/docs about {topic}. Analyze ALL of them and return a JSON array of summaries.

{article_blocks}

Return a JSON array with one object per article:
[
  {{
    "article_index": 0,
    "summary": "comprehensive 3-5 paragraph technical summary",
    "key_points": ["5-8 key takeaways"],
    "architecture_details": "any architecture, system design, or internal details (empty string if none)",
    "use_cases": ["real-world use cases or applications mentioned"]
  }}
]

Be thorough. Capture architecture diagrams described in text, design decisions, component interactions, data flows, and practical insights. Return ONLY valid JSON."""


def summarize_pages(
    pages: list[ScrapedPage], topic: str
) -> list[ArticleSummary]:
    """Summarize ALL scraped pages in a single Gemini API call."""
    if not pages:
        return []

    model = _get_model()

    chars_budget = 90000
    article_blocks = []
    chars_used = 0

    for i, page in enumerate(pages):
        per_article = chars_budget // len(pages)
        content = truncate_text(page.content, max_chars=per_article)
        block = (
            f"=== ARTICLE {i} ===\n"
            f"TITLE: {page.title}\n"
            f"SOURCE: {page.url}\n"
            f"CONTENT:\n{content}\n"
        )
        chars_used += len(block)
        if chars_used > chars_budget:
            logger.info(f"Truncating at {i} articles to fit context window")
            break
        article_blocks.append(block)

    prompt = BATCH_PROMPT.format(
        topic=topic,
        article_blocks="\n".join(article_blocks),
    )

    logger.info(
        f"Summarizing {len(article_blocks)} articles in 1 Gemini call "
        f"(~{len(prompt)} chars)"
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
            idx = item.get("article_index", len(summaries))
            if idx < len(pages):
                page = pages[idx]
            elif summaries:
                continue
            else:
                page = pages[0]

            summaries.append(ArticleSummary(
                title=page.title,
                url=page.url,
                domain=page.domain,
                summary=item.get("summary", ""),
                key_points=item.get("key_points", []),
                architecture_details=item.get("architecture_details", ""),
                use_cases=item.get("use_cases", []),
            ))

        logger.info(f"Summarized {len(summaries)} articles in 1 API call")
        return summaries

    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        raise

"""Web scraper: extracts readable text content from blog posts and documentation pages."""

import logging
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 30


@dataclass
class ScrapedPage:
    url: str
    title: str
    content: str
    domain: str
    word_count: int
    success: bool
    error: str | None = None


def _extract_text(soup: BeautifulSoup) -> str:
    """Extract the main readable text from a parsed HTML page."""
    for tag in soup(["script", "style", "nav", "footer", "header", "aside",
                     "iframe", "noscript", "meta", "link"]):
        tag.decompose()

    main = (
        soup.find("article")
        or soup.find("main")
        or soup.find("div", class_=re.compile(r"content|post|article|blog|entry|doc", re.I))
        or soup.find("div", id=re.compile(r"content|post|article|blog|entry|doc", re.I))
        or soup.body
    )
    if not main:
        main = soup

    lines = []
    for el in main.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li",
                              "td", "th", "pre", "code", "blockquote"]):
        text = el.get_text(separator=" ", strip=True)
        if not text or len(text) < 3:
            continue

        if el.name.startswith("h"):
            level = int(el.name[1])
            prefix = "#" * level
            lines.append(f"\n{prefix} {text}\n")
        elif el.name in ("pre", "code"):
            lines.append(f"\n```\n{text}\n```\n")
        elif el.name == "li":
            lines.append(f"- {text}")
        else:
            lines.append(text)

    full = "\n".join(lines)
    full = re.sub(r"\n{3,}", "\n\n", full)
    return full.strip()


def scrape_url(url: str) -> ScrapedPage:
    """Fetch and extract readable content from a single URL."""
    domain = urlparse(url).netloc
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else domain

        content = _extract_text(soup)
        word_count = len(content.split())

        if word_count < 20:
            return ScrapedPage(
                url=url, title=title, content="", domain=domain,
                word_count=0, success=False,
                error="Page has too little readable content",
            )

        logger.info(f"Scraped: '{title}' ({word_count} words) from {domain}")
        return ScrapedPage(
            url=url, title=title, content=content, domain=domain,
            word_count=word_count, success=True,
        )

    except Exception as e:
        logger.warning(f"Failed to scrape {url}: {e}")
        return ScrapedPage(
            url=url, title="", content="", domain=domain,
            word_count=0, success=False, error=str(e),
        )


def scrape_all(urls: list[str]) -> list[ScrapedPage]:
    """Scrape all URLs and return successfully extracted pages."""
    results = []
    for url in urls:
        page = scrape_url(url)
        if page.success:
            results.append(page)

    logger.info(f"Scraped {len(results)}/{len(urls)} pages successfully")
    return results

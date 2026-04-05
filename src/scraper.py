"""Web scraper: extracts readable text content from blog posts and documentation pages.

Handles common issues:
- Sites that block basic requests (rotates user agents, uses session)
- Pages with little content in article tags (falls back to full body text)
- Non-HTML responses (PDFs, etc.)
- Detailed error reporting per URL
"""

import logging
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]
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


def _get_headers(idx: int = 0) -> dict:
    return {
        "User-Agent": USER_AGENTS[idx % len(USER_AGENTS)],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


def _extract_text(soup: BeautifulSoup) -> str:
    """Extract the main readable text from a parsed HTML page."""
    for tag in soup(["script", "style", "nav", "footer", "aside",
                     "iframe", "noscript", "svg", "button", "form"]):
        tag.decompose()

    # Try progressively broader selectors to find the main content
    main = None
    selectors = [
        lambda s: s.find("article"),
        lambda s: s.find("main"),
        lambda s: s.find("div", class_=re.compile(r"content|post|article|blog|entry|doc|text|body", re.I)),
        lambda s: s.find("div", id=re.compile(r"content|post|article|blog|entry|doc|text|body|main", re.I)),
        lambda s: s.find("div", role="main"),
        lambda s: s.body,
    ]
    for selector in selectors:
        candidate = selector(soup)
        if candidate:
            test_text = candidate.get_text(strip=True)
            if len(test_text) > 100:
                main = candidate
                break

    if not main:
        main = soup

    lines = []
    for el in main.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li",
                              "td", "th", "pre", "code", "blockquote",
                              "span", "div"]):
        # Skip deeply nested divs/spans to avoid duplicates, but include leaf nodes
        if el.name in ("div", "span"):
            if el.find(["p", "h1", "h2", "h3", "h4", "li"]):
                continue

        text = el.get_text(separator=" ", strip=True)
        if not text or len(text) < 5:
            continue

        if el.name.startswith("h"):
            level = int(el.name[1])
            prefix = "#" * level
            lines.append(f"\n{prefix} {text}\n")
        elif el.name in ("pre", "code"):
            if len(text) > 10:
                lines.append(f"\n```\n{text}\n```\n")
        elif el.name == "li":
            lines.append(f"- {text}")
        else:
            lines.append(text)

    full = "\n".join(lines)
    full = re.sub(r"\n{3,}", "\n\n", full)
    return full.strip()


def _extract_text_fallback(html: str) -> str:
    """Last-resort: strip all HTML tags and return raw text."""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.I)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def scrape_url(url: str, attempt: int = 0) -> ScrapedPage:
    """Fetch and extract readable content from a single URL."""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    domain = urlparse(url).netloc

    try:
        session = requests.Session()
        resp = session.get(
            url,
            headers=_get_headers(attempt),
            timeout=TIMEOUT,
            allow_redirects=True,
        )
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            logger.warning(f"Non-HTML content ({content_type}) from {url}")
            # Still try to extract if it looks like text
            if "text/" not in content_type:
                return ScrapedPage(
                    url=url, title=domain, content="", domain=domain,
                    word_count=0, success=False,
                    error=f"Non-HTML content type: {content_type}",
                )

        html = resp.text
        if len(html) < 100:
            return ScrapedPage(
                url=url, title=domain, content="", domain=domain,
                word_count=0, success=False,
                error=f"Response too short ({len(html)} chars)",
            )

        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else domain

        content = _extract_text(soup)
        word_count = len(content.split())

        # If structured extraction got too little, try raw text fallback
        if word_count < 50:
            fallback_text = _extract_text_fallback(html)
            fallback_words = len(fallback_text.split())
            if fallback_words > word_count:
                content = fallback_text[:50000]
                word_count = len(content.split())
                logger.info(f"Used fallback extraction for {url}: {word_count} words")

        if word_count < 20:
            return ScrapedPage(
                url=url, title=title, content="", domain=domain,
                word_count=0, success=False,
                error=f"Too little readable content ({word_count} words). Page may require JavaScript.",
            )

        logger.info(f"Scraped: '{title}' ({word_count} words) from {domain}")
        return ScrapedPage(
            url=url, title=title, content=content, domain=domain,
            word_count=word_count, success=True,
        )

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        error_msg = f"HTTP {status}"
        if status == 403:
            error_msg = "403 Forbidden - site blocks automated access"
        elif status == 404:
            error_msg = "404 Not Found - check the URL"
        elif status == 429:
            error_msg = "429 Too Many Requests - try again later"
        logger.warning(f"HTTP error for {url}: {error_msg}")
        return ScrapedPage(
            url=url, title="", content="", domain=domain,
            word_count=0, success=False, error=error_msg,
        )

    except requests.exceptions.ConnectionError:
        error_msg = "Connection failed - check the URL"
        logger.warning(f"Connection error for {url}")
        return ScrapedPage(
            url=url, title="", content="", domain=domain,
            word_count=0, success=False, error=error_msg,
        )

    except requests.exceptions.Timeout:
        error_msg = "Request timed out"
        logger.warning(f"Timeout for {url}")
        return ScrapedPage(
            url=url, title="", content="", domain=domain,
            word_count=0, success=False, error=error_msg,
        )

    except Exception as e:
        logger.warning(f"Failed to scrape {url}: {type(e).__name__}: {e}")
        return ScrapedPage(
            url=url, title="", content="", domain=domain,
            word_count=0, success=False, error=f"{type(e).__name__}: {e}",
        )


def scrape_all(urls: list[str]) -> list[ScrapedPage]:
    """Scrape all URLs and return successfully extracted pages."""
    results = []
    failed = []
    for i, url in enumerate(urls):
        page = scrape_url(url, attempt=i)
        if page.success:
            results.append(page)
        else:
            failed.append(page)

    if failed:
        logger.warning(
            f"Failed URLs ({len(failed)}):\n" +
            "\n".join(f"  - {p.url}: {p.error}" for p in failed)
        )

    logger.info(f"Scraped {len(results)}/{len(urls)} pages successfully")
    return results

"""
Generic BeautifulSoup scraper — fallback for custom career pages.

Supports optional CSS selectors in config.yaml:
  selectors:
    job_links: "a.job-listing"   # selector for each <a> that wraps a job
    title: ".job-title"          # selector for title *within* each link element (optional)

If no selectors are provided, a heuristic scan is used:
  - Finds all <a> tags whose href contains job-path keywords
  - Filters to those whose link text matches a category keyword
"""

import requests
from datetime import date
from bs4 import BeautifulSoup
from urllib.parse import urljoin

REQUEST_TIMEOUT = 20

JOB_PATH_KEYWORDS = ("/job", "/jobs/", "/career", "/careers/", "/position", "/opening", "/vacancy", "/role/")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def _href_looks_like_job(href: str) -> bool:
    href_lower = href.lower()
    return any(kw in href_lower for kw in JOB_PATH_KEYWORDS)


def _matches_categories(text: str, categories: list[str]) -> str | None:
    text_lower = text.lower()
    for cat in categories:
        if cat.lower() in text_lower:
            return cat
    return None


def _scrape_with_selectors(soup: BeautifulSoup, selectors: dict, base_url: str,
                            categories: list[str], seen_urls: set[str], company_name: str,
                            today: str) -> list[dict]:
    job_link_sel = selectors.get("job_links", "a")
    title_sel = selectors.get("title")

    new_postings = []
    for tag in soup.select(job_link_sel):
        href = tag.get("href", "")
        if not href:
            continue

        job_url = urljoin(base_url, href)
        if job_url in seen_urls:
            continue

        if title_sel:
            title_tag = tag.select_one(title_sel)
            title = title_tag.get_text(strip=True) if title_tag else tag.get_text(strip=True)
        else:
            title = tag.get_text(strip=True)

        if not title:
            continue

        category = _matches_categories(title, categories)
        if not category:
            continue

        new_postings.append({
            "date_found": today,
            "company": company_name,
            "title": title,
            "category": category,
            "location": "",
            "posted_date": "",
            "url": job_url,
            "status": "New",
            "notes": "",
        })
        seen_urls.add(job_url)

    return new_postings


def _scrape_heuristic(soup: BeautifulSoup, base_url: str, categories: list[str],
                      seen_urls: set[str], company_name: str, today: str) -> list[dict]:
    new_postings = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        if not _href_looks_like_job(href):
            continue

        job_url = urljoin(base_url, href)
        if job_url in seen_urls:
            continue

        title = tag.get_text(strip=True)
        if not title:
            continue

        category = _matches_categories(title, categories)
        if not category:
            continue

        new_postings.append({
            "date_found": today,
            "company": company_name,
            "title": title,
            "category": category,
            "location": "",
            "posted_date": "",
            "url": job_url,
            "status": "New",
            "notes": "",
        })
        seen_urls.add(job_url)

    return new_postings


def _is_js_shell(html: str) -> bool:
    """Return True if the page is a JavaScript app shell with no real content."""
    soup = BeautifulSoup(html, "html.parser")
    body = soup.body
    if not body:
        return True
    return len(body.get_text(strip=True)) < 200


def scrape(company_cfg: dict, categories: list[str], seen_urls: set[str]) -> list[dict]:
    """
    Scrape a generic career page with BeautifulSoup and return new postings.
    Automatically falls back to a headless browser for JavaScript-rendered sites.

    Args:
        company_cfg:  Dict from config.yaml (must have 'url'; optional 'selectors').
        categories:   List of keyword strings to filter job titles against.
        seen_urls:    Set of URLs already recorded (for deduplication).

    Returns:
        List of posting dicts ready for sheets.append_postings().
    """
    company_name = company_cfg["name"]
    url = company_cfg.get("url", "")
    selectors = company_cfg.get("selectors")

    print(f"[generic] Fetching {company_name}...")

    html = None
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        html = resp.text
    except requests.RequestException as e:
        print(f"[generic] ERROR fetching {company_name}: {e}")
        return []

    # If the page is a JavaScript shell, render it with a real browser
    if _is_js_shell(html):
        print(f"[generic] {company_name}: JavaScript-rendered site detected — using browser...")
        from .browser import fetch_rendered_html
        rendered = fetch_rendered_html(url)
        if rendered:
            html = rendered
        else:
            print(f"[generic] {company_name}: browser render failed — no results")
            return []

    soup = BeautifulSoup(html, "html.parser")
    today = str(date.today())

    if selectors:
        new_postings = _scrape_with_selectors(soup, selectors, url, categories, seen_urls, company_name, today)
    else:
        new_postings = _scrape_heuristic(soup, url, categories, seen_urls, company_name, today)

    print(f"[generic] {company_name}: {len(new_postings)} new matching role(s)")
    return new_postings

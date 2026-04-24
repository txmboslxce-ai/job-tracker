"""
Lever scraper — uses the public Lever Postings API.

Endpoint: https://api.lever.co/v0/postings/{company}?mode=json
No authentication required. Returns all published roles.
"""

import requests
from datetime import date, datetime

API_URL = "https://api.lever.co/v0/postings/{company}?mode=json"
REQUEST_TIMEOUT = 15


def _matches_categories(title: str, team: str, categories: list[str]) -> str | None:
    """Return the first matching category keyword found in title or team, or None."""
    haystack = f"{title} {team}".lower()
    for cat in categories:
        if cat.lower() in haystack:
            return cat
    return None


def _parse_posted_date(created_at_ms: int | None) -> str:
    """Convert Lever epoch-milliseconds timestamp to YYYY-MM-DD."""
    if not created_at_ms:
        return ""
    try:
        return datetime.utcfromtimestamp(created_at_ms / 1000).strftime("%Y-%m-%d")
    except (ValueError, OSError):
        return ""


def scrape(company_cfg: dict, categories: list[str], seen_urls: set[str]) -> list[dict]:
    """
    Fetch all open postings for a Lever-hosted company and return new postings.

    Args:
        company_cfg:  Dict from config.yaml (must have 'lever_id' or falls back to lowercased name).
        categories:   List of keyword strings to filter job titles/teams against.
        seen_urls:    Set of URLs already recorded (for deduplication).

    Returns:
        List of posting dicts ready for sheets.append_postings().
    """
    lever_id = company_cfg.get("lever_id") or company_cfg["name"].lower().replace(" ", "")
    company_name = company_cfg["name"]
    url = API_URL.format(company=lever_id)

    print(f"[lever] Fetching {company_name} ({lever_id})...")

    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[lever] ERROR fetching {company_name}: {e}")
        return []

    jobs = resp.json()
    if not isinstance(jobs, list):
        print(f"[lever] Unexpected response format for {company_name}")
        return []

    print(f"[lever] {company_name}: {len(jobs)} total open roles")

    new_postings = []
    today = str(date.today())

    for job in jobs:
        title = job.get("text", "")
        job_url = job.get("hostedUrl", "")

        if not job_url or job_url in seen_urls:
            continue

        cats = job.get("categories", {})
        team = cats.get("team", "") or cats.get("department", "")
        location = cats.get("location", "") or cats.get("allLocations", [""])[0] if isinstance(cats.get("allLocations"), list) else ""

        category = _matches_categories(title, team, categories)
        if not category:
            continue

        posting = {
            "date_found": today,
            "company": company_name,
            "title": title,
            "category": category,
            "location": location,
            "posted_date": _parse_posted_date(job.get("createdAt")),
            "url": job_url,
            "status": "New",
            "notes": "",
        }
        new_postings.append(posting)
        seen_urls.add(job_url)

    print(f"[lever] {company_name}: {len(new_postings)} new matching role(s)")
    return new_postings

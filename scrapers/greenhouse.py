"""
Greenhouse scraper — uses the public Greenhouse Jobs Board JSON API.

Endpoint: https://boards-api.greenhouse.io/v1/boards/{greenhouse_id}/jobs?content=true
No authentication required. Returns all open roles with full metadata.
"""

import requests
from datetime import date, datetime

API_URL = "https://boards-api.greenhouse.io/v1/boards/{greenhouse_id}/jobs?content=true"
REQUEST_TIMEOUT = 15


def _matches_categories(title: str, categories: list[str]) -> str | None:
    """Return the first matching category keyword found in the job title, or None."""
    title_lower = title.lower()
    for cat in categories:
        if cat.lower() in title_lower:
            return cat
    return None


def _parse_posted_date(updated_at: str) -> str:
    """Convert Greenhouse ISO timestamp to YYYY-MM-DD, or return empty string."""
    if not updated_at:
        return ""
    try:
        return datetime.fromisoformat(updated_at.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return ""


def scrape(company_cfg: dict, categories: list[str], seen_urls: set[str]) -> list[dict]:
    """
    Fetch all open jobs for a Greenhouse-hosted company and return new postings.

    Args:
        company_cfg:  Dict from config.yaml for this company (must have 'greenhouse_id').
        categories:   List of keyword strings to filter job titles against.
        seen_urls:    Set of URLs already recorded (for deduplication).

    Returns:
        List of posting dicts ready for sheets.append_postings().
    """
    greenhouse_id = company_cfg.get("greenhouse_id") or company_cfg.get("name", "").lower()
    company_name = company_cfg["name"]
    url = API_URL.format(greenhouse_id=greenhouse_id)

    print(f"[greenhouse] Fetching {company_name} ({greenhouse_id})...")

    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[greenhouse] ERROR fetching {company_name}: {e}")
        return []

    data = resp.json()
    jobs = data.get("jobs", [])
    print(f"[greenhouse] {company_name}: {len(jobs)} total open roles")

    new_postings = []
    today = str(date.today())

    for job in jobs:
        title = job.get("title", "")
        job_url = job.get("absolute_url", "")

        if not job_url or job_url in seen_urls:
            continue

        category = _matches_categories(title, categories)
        if not category:
            continue

        location_parts = job.get("location", {})
        location = location_parts.get("name", "") if isinstance(location_parts, dict) else ""

        posting = {
            "date_found": today,
            "company": company_name,
            "title": title,
            "category": category,
            "location": location,
            "posted_date": _parse_posted_date(job.get("updated_at", "")),
            "url": job_url,
            "status": "New",
            "notes": "",
        }
        new_postings.append(posting)
        seen_urls.add(job_url)

    print(f"[greenhouse] {company_name}: {len(new_postings)} new matching role(s)")
    return new_postings

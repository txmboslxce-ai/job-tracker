"""
Workday scraper — uses the internal Workday CXS JSON API.

The public-facing Workday URL follows this pattern:
  https://{tenant}.{instance}.myworkdayjobs.com/en-US/{site}

We derive the internal API endpoint from it:
  https://{tenant}.{instance}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs

Config entry example:
  - name: Acme Corp
    platform: workday
    url: https://acme.wd1.myworkdayjobs.com/en-US/AcmeCareers
"""

import re
import requests
from datetime import date
from urllib.parse import urlparse

REQUEST_TIMEOUT = 20
PAGE_SIZE = 20

# Workday returns relative external paths; we prepend the base URL
_LOCALE_RE = re.compile(r"^[a-z]{2}-[A-Z]{2}$")


def _derive_api_url(public_url: str) -> tuple[str, str] | tuple[None, None]:
    """
    Parse the public Workday board URL and return (api_url, base_url).
    Returns (None, None) if the URL can't be parsed.
    """
    parsed = urlparse(public_url)
    hostname = parsed.hostname or ""
    parts = hostname.split(".")

    # Expect: tenant.wdN.myworkdayjobs.com
    if len(parts) < 4 or "myworkdayjobs" not in parts:
        return None, None

    tenant = parts[0]
    instance = parts[1]
    base_url = f"https://{tenant}.{instance}.myworkdayjobs.com"

    # Path segments, skipping locale (e.g. en-US)
    path_parts = [p for p in parsed.path.split("/") if p and not _LOCALE_RE.match(p)]
    if not path_parts:
        return None, None

    site = path_parts[0]
    api_url = f"{base_url}/wday/cxs/{tenant}/{site}/jobs"
    return api_url, base_url


def _fetch_page(api_url: str, offset: int) -> dict:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "appliedFacets": {},
        "limit": PAGE_SIZE,
        "offset": offset,
        "searchText": "",
    }
    resp = requests.post(api_url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _matches_categories(title: str, categories: list[str]) -> str | None:
    title_lower = title.lower()
    for cat in categories:
        if cat.lower() in title_lower:
            return cat
    return None


def scrape(company_cfg: dict, categories: list[str], seen_urls: set[str]) -> list[dict]:
    """
    Fetch all open jobs for a Workday-hosted company and return new postings.

    Args:
        company_cfg:  Dict from config.yaml (must have 'url' pointing to the public Workday board).
        categories:   List of keyword strings to filter job titles against.
        seen_urls:    Set of URLs already recorded (for deduplication).

    Returns:
        List of posting dicts ready for sheets.append_postings().
    """
    company_name = company_cfg["name"]
    public_url = company_cfg.get("url", "")

    api_url, base_url = _derive_api_url(public_url)
    if not api_url:
        print(f"[workday] ERROR: could not derive API URL from '{public_url}' for {company_name}")
        return []

    print(f"[workday] Fetching {company_name}...")

    all_jobs = []
    offset = 0

    try:
        while True:
            data = _fetch_page(api_url, offset)
            page = data.get("jobPostings", [])
            total = data.get("total", 0)
            all_jobs.extend(page)
            offset += len(page)
            if offset >= total or not page:
                break
    except requests.RequestException as e:
        print(f"[workday] ERROR fetching {company_name}: {e}")
        if not all_jobs:
            return []

    print(f"[workday] {company_name}: {len(all_jobs)} total open roles")

    new_postings = []
    today = str(date.today())

    for job in all_jobs:
        title = job.get("title", "")
        external_path = job.get("externalPath", "")

        if not external_path:
            continue

        job_url = base_url + external_path
        if job_url in seen_urls:
            continue

        category = _matches_categories(title, categories)
        if not category:
            continue

        location = job.get("locationsText", "")

        # Workday posts dates as human strings like "Posted 3 Days Ago" — store as-is
        posted_on = job.get("postedOn", "")

        posting = {
            "date_found": today,
            "company": company_name,
            "title": title,
            "category": category,
            "location": location,
            "posted_date": posted_on,
            "url": job_url,
            "status": "New",
            "notes": "",
        }
        new_postings.append(posting)
        seen_urls.add(job_url)

    print(f"[workday] {company_name}: {len(new_postings)} new matching role(s)")
    return new_postings

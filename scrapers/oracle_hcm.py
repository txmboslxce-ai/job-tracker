"""
Oracle Recruiting Cloud scraper — uses the ORC REST API.

Oracle Recruiting Cloud URLs follow this pattern:
  https://{company-domain}/en/sites/{siteId}/jobs

We call the public REST API endpoint:
  GET https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions
    ?finder=findReqs;siteNumber={siteId},sortBy=POSTING_DATES_DESC,...
    &limit=100&offset=0&totalResults=true
"""

import re
import requests
from datetime import date
from urllib.parse import urlparse

REQUEST_TIMEOUT = 20
PAGE_SIZE = 100

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def _extract_site_id(url: str) -> str:
    """Extract siteNumber from Oracle Recruiting Cloud URL."""
    m = re.search(r"/en/sites/([^/?#]+)", url)
    return m.group(1) if m else "CX_1"


def _matches_categories(title: str, categories: list[str]) -> str | None:
    title_lower = title.lower()
    for cat in categories:
        if cat.lower() in title_lower:
            return cat
    return None


def scrape(company_cfg: dict, categories: list[str], seen_urls: set[str]) -> list[dict]:
    """
    Fetch all open jobs from an Oracle Recruiting Cloud site and return new postings.

    Args:
        company_cfg:  Dict from config / Companies sheet (must have 'url').
        categories:   List of keyword strings to filter job titles against.
        seen_urls:    Set of URLs already recorded (for deduplication).
    """
    company_name = company_cfg["name"]
    url = company_cfg.get("url", "")

    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    site_id = _extract_site_id(url)

    api_url = f"{base}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
    print(f"[oracle_hcm] Fetching {company_name} (site={site_id})...")

    all_jobs: list[dict] = []
    offset = 0

    while True:
        params = {
            "expand": "requisitionList.secondaryLocations,flexFieldsFacet.values",
            "finder": (
                f"findReqs;siteNumber={site_id},"
                "sortBy=POSTING_DATES_DESC,"
                "lastSelectedFacet=TITLES,"
                "selectedTitlesFacet="
            ),
            "limit": PAGE_SIZE,
            "offset": offset,
            "totalResults": "true",
        }
        try:
            resp = requests.get(api_url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[oracle_hcm] {company_name}: API error — {e}")
            break

        items = data.get("items", [])
        if not items:
            break

        req_list = items[0].get("requisitionList", {})
        jobs = req_list.get("items", [])
        if not jobs:
            break

        all_jobs.extend(jobs)
        total = req_list.get("totalResults", len(jobs))
        offset += len(jobs)
        if offset >= total or len(jobs) < PAGE_SIZE:
            break

    print(f"[oracle_hcm] {company_name}: {len(all_jobs)} total open roles")

    new_postings: list[dict] = []
    today = str(date.today())

    for job in all_jobs:
        title = job.get("Title") or job.get("title", "")
        if not title:
            continue

        category = _matches_categories(title, categories)
        if not category:
            continue

        # Prefer an explicit URL from the API; otherwise build from ID + slug
        job_url = job.get("ExternalApplyURL") or job.get("externalApplyURL", "")
        if not job_url:
            job_id = str(job.get("Id") or job.get("id", "")).strip()
            slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            job_url = f"{base}/en/sites/{site_id}/jobs/{job_id}/{slug}" if job_id else ""

        if not job_url or job_url in seen_urls:
            continue

        location = job.get("PrimaryLocation") or job.get("primaryLocation", "")
        posted = (
            job.get("PostingDate") or job.get("PostedDate") or job.get("postedDate", "")
        )
        if posted and "T" in str(posted):
            posted = str(posted).split("T")[0]

        new_postings.append({
            "date_found": today,
            "company": company_name,
            "title": title,
            "category": category,
            "location": str(location),
            "posted_date": str(posted),
            "url": job_url,
            "status": "New",
            "notes": "",
        })
        seen_urls.add(job_url)

    print(f"[oracle_hcm] {company_name}: {len(new_postings)} new matching role(s)")
    return new_postings

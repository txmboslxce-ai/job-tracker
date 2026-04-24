"""Scraper dispatcher — routes each company to the right platform scraper."""

from .greenhouse import scrape as _greenhouse
from .lever import scrape as _lever
from .workday import scrape as _workday
from .oracle_hcm import scrape as _oracle_hcm
from .generic import scrape as _generic

_SCRAPERS = {
    "greenhouse": _greenhouse,
    "lever": _lever,
    "workday": _workday,
    "oracle_hcm": _oracle_hcm,
    "generic": _generic,
}


def scrape_company(company_cfg: dict, categories: list[str], seen_urls: set[str]) -> list[dict]:
    """Dispatch to the correct scraper based on company_cfg['platform']."""
    platform = company_cfg.get("platform", "generic")
    fn = _SCRAPERS.get(platform)
    if fn is None:
        print(f"[scrapers] Unknown platform '{platform}' for {company_cfg.get('name', '?')} — skipping")
        return []
    return fn(company_cfg, categories, seen_urls)

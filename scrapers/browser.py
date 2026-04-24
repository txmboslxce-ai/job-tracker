"""
Playwright-based HTML renderer for JavaScript-heavy career pages.

Falls back gracefully if Playwright is not installed (e.g. Python 3.14 locally).
Auto-installs the Chromium browser binary on first use.
"""

import functools
import subprocess
import sys


@functools.lru_cache(maxsize=1)
def _install_chromium() -> None:
    """Download the Playwright Chromium binary — runs once per process."""
    try:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            timeout=120,
            check=False,
        )
    except Exception:
        pass


def fetch_rendered_html(url: str, timeout_ms: int = 30_000) -> str | None:
    """
    Load a URL in a headless Chromium browser and return the fully-rendered HTML.
    Returns None if Playwright is unavailable or the request fails.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    _install_chromium()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            html = page.content()
            browser.close()
        return html
    except Exception as e:
        print(f"[browser] Could not render {url}: {e}")
        return None

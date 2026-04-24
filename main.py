"""
Job Tracker — main runner.

Usage:
    python main.py                   # normal run
    python main.py --no-email        # skip email digest
    python main.py --dry-run         # scrape only, no Sheet writes, no email
"""

import argparse
import sys
import yaml

import sheets
import notifier
from scrapers import scrape_company

SEEN_URLS_FILE = "seen_urls.txt"
CONFIG_FILE = "config.yaml"


# ---------------------------------------------------------------------------
# seen_urls helpers
# ---------------------------------------------------------------------------

def load_seen_urls() -> set[str]:
    """Load the local deduplication cache from seen_urls.txt."""
    try:
        with open(SEEN_URLS_FILE, encoding="utf-8") as f:
            return {line.strip() for line in f if line.strip() and not line.startswith("#")}
    except FileNotFoundError:
        return set()


def save_seen_urls(urls: set[str]) -> None:
    """Persist the updated deduplication cache."""
    with open(SEEN_URLS_FILE, "w", encoding="utf-8") as f:
        f.write("# One URL per line. Managed automatically by main.py — do not edit manually.\n")
        for url in sorted(urls):
            f.write(url + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Job posting tracker")
    parser.add_argument("--no-email", action="store_true", help="Skip sending the email digest")
    parser.add_argument("--dry-run", action="store_true", help="Scrape only — no Sheets writes, no email")
    args = parser.parse_args()

    # Load config
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"ERROR: {CONFIG_FILE} not found. Copy config.yaml and fill in your values.")
        return 1

    gs_cfg = config["google_sheets"]
    categories = config.get("categories", [])
    companies = config.get("companies", [])
    email_cfg = config.get("email", {})

    if not companies:
        print("No companies configured in config.yaml — nothing to do.")
        return 0

    # Connect to Sheets (skip in dry-run)
    sheet = None
    if not args.dry_run:
        print("[main] Connecting to Google Sheets...")
        try:
            sheet = sheets.connect(gs_cfg["credentials_path"], gs_cfg["sheet_id"])
        except Exception as e:
            print(f"[main] ERROR connecting to Sheets: {e}")
            return 1

    # Prefer companies saved via the web UI (Companies tab) over config.yaml
    if sheet is not None:
        try:
            companies_ws = sheets.get_companies_tab(sheet)
            sheet_companies = sheets.load_companies(companies_ws)
            if sheet_companies:
                companies = sheet_companies
                print(f"[main] Loaded {len(companies)} company/companies from Sheet Companies tab.")
            else:
                print(f"[main] Companies tab empty — using {len(companies)} from config.yaml.")
        except Exception as e:
            print(f"[main] Could not read Companies tab ({e}) — using config.yaml.")

    # Build deduplication set: file cache ∪ sheet URLs
    seen_urls = load_seen_urls()
    if sheet is not None:
        sheet_urls = sheets.get_existing_urls(sheet)
        before = len(seen_urls)
        seen_urls |= sheet_urls
        added = len(seen_urls) - before
        if added:
            print(f"[main] Loaded {added} additional URL(s) from Sheet.")
    print(f"[main] Deduplication cache: {len(seen_urls)} known URL(s).")

    # Scrape all companies
    all_new: list[dict] = []
    for company in companies:
        try:
            new = scrape_company(company, categories, seen_urls)
            all_new.extend(new)
        except Exception as e:
            print(f"[main] ERROR scraping {company.get('name', '?')}: {e}")

    print(f"\n[main] Total new postings found: {len(all_new)}")

    if args.dry_run:
        print("[main] Dry run — skipping Sheet writes and email.")
        if all_new:
            print("\nPostings that would have been logged:")
            for p in all_new:
                print(f"  {p['company']:30} {p['title']}")
        return 0

    # Write to Sheets
    if all_new:
        print(f"[main] Writing {len(all_new)} posting(s) to Sheet...")
        try:
            sheets.append_postings(sheet, all_new)
        except Exception as e:
            print(f"[main] ERROR writing to Sheet: {e}")
            return 1

        # Persist updated cache
        save_seen_urls(seen_urls)
        print(f"[main] seen_urls.txt updated ({len(seen_urls)} total URLs).")

        # Send email digest
        if not args.no_email:
            notifier.send_digest(all_new, email_cfg)
    else:
        print("[main] Nothing new — Sheet and email unchanged.")
        # Still save cache in case Sheet URLs were merged in
        save_seen_urls(seen_urls)

    print("\n[main] Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

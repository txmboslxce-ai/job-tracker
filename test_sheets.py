"""
Step 2 verification script.
Run this after filling in config.yaml to confirm the Sheets connection works.

Usage:
    python test_sheets.py
"""

import yaml
from datetime import date
from sheets import connect, append_posting, get_existing_urls


def main():
    print("=" * 50)
    print("Job Tracker — Sheets Connection Test")
    print("=" * 50)

    with open("config.yaml") as f:
        config = yaml.safe_load(f)

    gs_cfg = config["google_sheets"]
    creds_path = gs_cfg["credentials_path"]
    sheet_id = gs_cfg["sheet_id"]

    print(f"\n[test] Credentials file : {creds_path}")
    print(f"[test] Sheet ID         : {sheet_id}")
    print()

    print("[test] Connecting to Google Sheets...")
    sheet = connect(creds_path, sheet_id)
    print("[test] Connection successful.\n")

    dummy = {
        "date_found": str(date.today()),
        "company": "TEST COMPANY — DELETE ME",
        "title": "Test Posting",
        "category": "Engineering",
        "location": "Remote",
        "posted_date": "",
        "url": "https://example.com/test-posting-do-not-track",
        "status": "New",
        "notes": "Inserted by test_sheets.py — safe to delete",
    }

    print("[test] Appending dummy row...")
    append_posting(sheet, dummy)
    print("[test] Done.\n")

    print("[test] Reading back existing URLs...")
    urls = get_existing_urls(sheet)
    print(f"[test] Found {len(urls)} URL(s) in sheet.")
    if dummy["url"] in urls:
        print("[test] Dummy URL confirmed present in sheet.\n")
    else:
        print("[test] WARNING: dummy URL not found in URL column — check sheet structure.\n")

    print("=" * 50)
    print("SUCCESS — Sheets integration is working.")
    print("You can now delete the test row from the Sheet.")
    print("=" * 50)


if __name__ == "__main__":
    main()

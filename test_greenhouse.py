"""
Step 3 verification script.
Tests the Greenhouse scraper against a known public Greenhouse board.

Usage:
    python test_greenhouse.py
"""

from scrapers.greenhouse import scrape

# Ashby (the ATS company) uses Greenhouse and has public postings — good smoke test
TEST_COMPANY = {
    "name": "Greenhouse (smoke test)",
    "greenhouse_id": "greenhouse",
    "platform": "greenhouse",
}

TEST_CATEGORIES = ["Engineer", "Software", "Data", "Product", "Developer", "IT"]


def main():
    print("=" * 50)
    print("Greenhouse Scraper Test")
    print("=" * 50)

    seen: set[str] = set()
    results = scrape(TEST_COMPANY, TEST_CATEGORIES, seen)

    if results:
        print(f"\nSample result (first match):")
        for k, v in results[0].items():
            print(f"  {k:15} {v}")
        print(f"\nTotal new postings found: {len(results)}")
        print("\nSUCCESS — Greenhouse scraper is working.")
    else:
        print("\nNo matching postings found.")
        print("This may mean the board is empty or no titles matched the test categories.")
        print("Try changing TEST_CATEGORIES or TEST_COMPANY.greenhouse_id.")

    print("=" * 50)


if __name__ == "__main__":
    main()

"""Google Sheets integration — connect, append rows, read existing URLs."""

import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

HEADERS = [
    "Date Found",
    "Company",
    "Job Title",
    "Category",
    "Location",
    "Posted Date",
    "URL",
    "Status",
    "Notes",
]


def _open_worksheet(client: gspread.Client, sheet_id: str) -> gspread.Worksheet:
    sheet = client.open_by_key(sheet_id).sheet1
    if sheet.row_count == 0 or sheet.cell(1, 1).value != HEADERS[0]:
        print("[sheets] Sheet is empty — writing header row.")
        sheet.insert_row(HEADERS, index=1)
    else:
        print(f"[sheets] Connected. Sheet already has {sheet.row_count} rows.")
    return sheet


def connect(credentials_path: str, sheet_id: str) -> gspread.Worksheet:
    """Authenticate via service account file and return the first worksheet."""
    creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
    return _open_worksheet(gspread.authorize(creds), sheet_id)


def connect_from_info(credentials_info: dict, sheet_id: str) -> gspread.Worksheet:
    """Authenticate via a credentials dict (used by Streamlit Cloud secrets) and return the first worksheet."""
    creds = Credentials.from_service_account_info(credentials_info, scopes=SCOPES)
    return _open_worksheet(gspread.authorize(creds), sheet_id)


def append_posting(sheet: gspread.Worksheet, posting: dict) -> None:
    """Append a single posting dict as a new row."""
    row = [
        posting.get("date_found", ""),
        posting.get("company", ""),
        posting.get("title", ""),
        posting.get("category", ""),
        posting.get("location", ""),
        posting.get("posted_date", ""),
        posting.get("url", ""),
        posting.get("status", "New"),
        posting.get("notes", ""),
    ]
    sheet.append_row(row, value_input_option="USER_ENTERED")
    print(f"[sheets] Appended: {posting.get('company')} — {posting.get('title')}")


def append_postings(sheet: gspread.Worksheet, postings: list[dict]) -> int:
    """Append a list of postings. Returns number of rows written."""
    for posting in postings:
        append_posting(sheet, posting)
    return len(postings)


def get_existing_urls(sheet: gspread.Worksheet) -> set[str]:
    """Return the set of all URLs already in the sheet (column 7)."""
    try:
        url_col = sheet.col_values(7)  # 1-indexed; column G = URL
        # Skip header row
        return set(u for u in url_col[1:] if u.strip())
    except gspread.exceptions.APIError as e:
        print(f"[sheets] Warning: could not read existing URLs — {e}")
        return set()

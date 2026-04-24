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


# ── Companies config tab ───────────────────────────────────────────────────

_COMPANIES_TAB = "Companies"
_COMPANIES_HEADERS = ["Name", "Platform", "URL", "greenhouse_id", "lever_id", "Active", "Keywords"]


def get_companies_tab(jobs_ws: gspread.Worksheet) -> gspread.Worksheet:
    """Return (or create) the Companies config tab on the same spreadsheet.
    Migrates existing tabs that pre-date the Keywords column."""
    spreadsheet = jobs_ws.spreadsheet
    try:
        ws = spreadsheet.worksheet(_COMPANIES_TAB)
        # Migration: add Keywords header if the column doesn't exist yet
        existing_headers = ws.row_values(1)
        if "Keywords" not in existing_headers:
            ws.update_cell(1, len(existing_headers) + 1, "Keywords")
        return ws
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(_COMPANIES_TAB, rows=200, cols=len(_COMPANIES_HEADERS))
        ws.insert_row(_COMPANIES_HEADERS, index=1)
        return ws


def load_all_companies_raw(companies_ws: gspread.Worksheet) -> list[tuple[int, dict]]:
    """Return all companies (active and paused) as (sheet_row_index, dict) pairs."""
    values = companies_ws.get_all_values()
    if len(values) <= 1:
        return []
    headers = [h.lower().replace(" ", "_") for h in values[0]]
    return [
        (i + 2, dict(zip(headers, row)))  # row 1 = header, data starts at row 2
        for i, row in enumerate(values[1:])
    ]


def load_companies(companies_ws: gspread.Worksheet) -> list[dict]:
    """Return active companies as config-compatible dicts (for scrapers)."""
    result = []
    for _, co in load_all_companies_raw(companies_ws):
        if str(co.get("active", "TRUE")).upper() == "FALSE":
            continue
        cfg: dict = {
            "name": co.get("name", ""),
            "platform": co.get("platform", "generic"),
            "url": co.get("url", ""),
            "keywords": co.get("keywords", ""),
        }
        if co.get("greenhouse_id"):
            cfg["greenhouse_id"] = co["greenhouse_id"]
        if co.get("lever_id"):
            cfg["lever_id"] = co["lever_id"]
        result.append(cfg)
    return result


def save_company(companies_ws: gspread.Worksheet, cfg: dict) -> None:
    """Append a new company row."""
    companies_ws.append_row(
        [cfg.get("name", ""), cfg.get("platform", "generic"), cfg.get("url", ""),
         cfg.get("greenhouse_id", ""), cfg.get("lever_id", ""), "TRUE",
         cfg.get("keywords", "")],
        value_input_option="USER_ENTERED",
    )


def toggle_company_active(companies_ws: gspread.Worksheet, row_idx: int, active: bool) -> None:
    """Flip the Active column for the given 1-based sheet row."""
    active_col = _COMPANIES_HEADERS.index("Active") + 1
    companies_ws.update_cell(row_idx, active_col, "TRUE" if active else "FALSE")


def delete_company_row(companies_ws: gspread.Worksheet, row_idx: int) -> None:
    """Delete a company row by its 1-based sheet row index."""
    companies_ws.delete_rows(row_idx)

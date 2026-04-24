"""Job Tracker — Streamlit web UI."""

import re
import yaml
import pandas as pd
import streamlit as st
from urllib.parse import urlparse

import sheets as sh
from scrapers import scrape_company

st.set_page_config(page_title="Job Tracker", page_icon="🔍", layout="wide")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def detect_platform(url: str) -> str:
    if "greenhouse.io" in url:
        return "greenhouse"
    if "lever.co" in url:
        return "lever"
    if "myworkdayjobs.com" in url:
        return "workday"
    return "generic"


def build_company_cfg(url: str, name: str, platform: str) -> dict:
    cfg = {"name": name, "platform": platform, "url": url}
    if platform == "greenhouse":
        # boards.greenhouse.io/{id}  or  job-boards.greenhouse.io/{id}
        path = urlparse(url).path.strip("/")
        cfg["greenhouse_id"] = path.split("/")[-1] if path else ""
    elif platform == "lever":
        # jobs.lever.co/{id}
        path = urlparse(url).path.strip("/")
        cfg["lever_id"] = path.split("/")[-1] if path else ""
    return cfg


@st.cache_resource(show_spinner=False)
def get_sheet():
    """Connect to Google Sheets — tries Streamlit secrets first, then local config."""
    try:
        creds_info = dict(st.secrets["gcp_service_account"])
        sheet_id = st.secrets["sheet_id"]
        return sh.connect_from_info(creds_info, sheet_id)
    except Exception:
        pass
    try:
        with open("config.yaml", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        gs = cfg["google_sheets"]
        return sh.connect(gs["credentials_path"], gs["sheet_id"])
    except Exception as e:
        return None


def parse_keywords(raw: str) -> list[str]:
    return [k.strip() for k in re.split(r"[\n,]+", raw) if k.strip()]


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

st.title("🔍 Job Tracker")
st.caption("Enter a careers page URL and keywords to find matching roles.")

with st.form("scan_form"):
    col1, col2 = st.columns([3, 1])
    with col1:
        url = st.text_input(
            "Careers page URL",
            placeholder="https://boards.greenhouse.io/acme  or  https://jobs.lever.co/acme  or any careers page",
        )
    with col2:
        company_name = st.text_input("Company name", placeholder="Acme Corp")

    keywords_raw = st.text_area(
        "Keywords — one per line or comma-separated (title must contain at least one)",
        value="Engineering\nSoftware\nDeveloper\nData\nProduct\nIT\nTechnology\nSystems\nInfrastructure\nDevOps\nCloud",
        height=160,
    )
    submitted = st.form_submit_button("Scan", type="primary", use_container_width=True)

if submitted:
    url = url.strip()
    company_name = company_name.strip() or url
    if not url:
        st.warning("Please enter a URL.")
    else:
        keywords = parse_keywords(keywords_raw)
        if not keywords:
            st.warning("Please enter at least one keyword.")
        else:
            platform = detect_platform(url)
            company_cfg = build_company_cfg(url, company_name, platform)

            with st.spinner(f"Scanning {company_name} ({platform})…"):
                seen: set[str] = set()
                try:
                    results = scrape_company(company_cfg, keywords, seen)
                    st.session_state["results"] = results
                    st.session_state["saved"] = False
                    st.session_state["scan_meta"] = {
                        "company": company_name,
                        "platform": platform,
                        "keywords": keywords,
                    }
                except Exception as e:
                    st.error(f"Scrape failed: {e}")
                    st.session_state["results"] = []

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

results: list[dict] | None = st.session_state.get("results")
meta = st.session_state.get("scan_meta", {})

if results is not None:
    st.divider()

    if not results:
        st.info(
            f"No roles matching your keywords were found at **{meta.get('company', 'that URL')}**.\n\n"
            "Try broadening your keywords, or check that the URL points to a job listings page."
        )
    else:
        platform_label = {"greenhouse": "Greenhouse", "lever": "Lever", "workday": "Workday", "generic": "careers page"}.get(meta.get("platform", ""), "")
        st.success(f"Found **{len(results)}** matching role(s) on {meta.get('company')}'s {platform_label}.")

        df = pd.DataFrame(results)[["company", "title", "category", "location", "posted_date", "url"]]
        df.columns = ["Company", "Title", "Category", "Location", "Posted", "URL"]

        st.dataframe(
            df,
            column_config={"URL": st.column_config.LinkColumn("URL", display_text="Open ↗")},
            use_container_width=True,
            hide_index=True,
        )

        col1, col2 = st.columns(2)

        with col1:
            sheet = get_sheet()
            if sheet is None:
                st.caption("Google Sheets not configured — set up secrets to enable saving.")
            elif st.session_state.get("saved"):
                st.success(f"✓ Saved {len(results)} posting(s) to Google Sheets.")
            else:
                if st.button("Save all to Google Sheet", type="primary", use_container_width=True):
                    existing = sh.get_existing_urls(sheet)
                    new_only = [p for p in results if p["url"] not in existing]
                    if not new_only:
                        st.info("All postings are already in the Sheet.")
                    else:
                        with st.spinner(f"Saving {len(new_only)} posting(s)…"):
                            sh.append_postings(sheet, new_only)
                        st.session_state["saved"] = True
                        st.rerun()

        with col2:
            csv = df.to_csv(index=False)
            st.download_button(
                "Download CSV",
                csv,
                file_name=f"{meta.get('company', 'jobs').replace(' ', '_')}_results.csv",
                mime="text/csv",
                use_container_width=True,
            )

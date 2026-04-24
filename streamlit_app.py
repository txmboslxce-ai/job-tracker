"""Job Tracker — Streamlit web UI."""

import re
import yaml
import pandas as pd
import streamlit as st
from urllib.parse import urlparse

import sheets as sh
from scrapers import scrape_company

st.set_page_config(page_title="Job Tracker", page_icon="🔍", layout="wide")

DEFAULT_KEYWORDS = (
    "Engineering\nSoftware\nDeveloper\nData\nProduct\nIT\n"
    "Technology\nSystems\nInfrastructure\nDevOps\nCloud"
)

PLATFORM_LABELS = {
    "greenhouse": "🌱 Greenhouse",
    "lever": "🔵 Lever",
    "workday": "💼 Workday",
    "generic": "🌐 Generic",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

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
        path = urlparse(url).path.strip("/")
        cfg["greenhouse_id"] = path.split("/")[-1] if path else ""
    elif platform == "lever":
        path = urlparse(url).path.strip("/")
        cfg["lever_id"] = path.split("/")[-1] if path else ""
    return cfg


def parse_keywords(raw: str) -> list[str]:
    return [k.strip() for k in re.split(r"[\n,]+", raw) if k.strip()]


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
    except Exception:
        return None


def render_results(results: list[dict], save_key: str, saved_key: str) -> None:
    """Render results table with Save to Sheet and Download CSV buttons."""
    df = pd.DataFrame(results)[["company", "title", "category", "location", "posted_date", "url"]]
    df.columns = ["Company", "Title", "Category", "Location", "Posted", "URL"]
    st.dataframe(
        df,
        column_config={"URL": st.column_config.LinkColumn("URL", display_text="Open ↗")},
        use_container_width=True,
        hide_index=True,
    )
    c1, c2 = st.columns(2)
    with c1:
        sheet = get_sheet()
        if sheet is None:
            st.caption("Google Sheets not configured.")
        elif st.session_state.get(saved_key):
            st.success("✓ Saved to Google Sheets.")
        else:
            if st.button("Save to Google Sheet", type="primary", use_container_width=True, key=save_key):
                existing = sh.get_existing_urls(sheet)
                new_only = [p for p in results if p["url"] not in existing]
                if not new_only:
                    st.info("All postings are already in the Sheet.")
                else:
                    with st.spinner(f"Saving {len(new_only)} posting(s)…"):
                        sh.append_postings(sheet, new_only)
                    st.session_state[saved_key] = True
                    st.rerun()
    with c2:
        st.download_button(
            "Download CSV", df.to_csv(index=False),
            file_name="job_results.csv", mime="text/csv",
            use_container_width=True, key=f"{save_key}_csv",
        )


# ── Layout ────────────────────────────────────────────────────────────────────

st.title("🔍 Job Tracker")

tab_scan, tab_companies, tab_run, tab_schedule = st.tabs(
    ["🔍 Scan", "🏢 Companies", "▶️ Run All", "⏰ Schedule"]
)


# ── TAB: Scan ─────────────────────────────────────────────────────────────────

with tab_scan:
    st.subheader("Scan a single careers page")

    with st.form("scan_form"):
        c1, c2 = st.columns([3, 1])
        with c1:
            scan_url = st.text_input(
                "Careers page URL",
                placeholder="https://boards.greenhouse.io/acme  ·  https://jobs.lever.co/acme  ·  any careers page",
            )
        with c2:
            scan_name = st.text_input("Company name", placeholder="Acme Corp")
        scan_keywords = st.text_area("Keywords", value=DEFAULT_KEYWORDS, height=150)
        submitted = st.form_submit_button("Scan", type="primary", use_container_width=True)

    if submitted:
        scan_url = scan_url.strip()
        if not scan_url:
            st.warning("Please enter a URL.")
        else:
            kws = parse_keywords(scan_keywords)
            platform = detect_platform(scan_url)
            cfg = build_company_cfg(scan_url, scan_name.strip() or scan_url, platform)
            with st.spinner(f"Scanning {PLATFORM_LABELS[platform]}…"):
                try:
                    results = scrape_company(cfg, kws, set())
                    st.session_state["scan_results"] = results
                    st.session_state["scan_saved"] = False
                except Exception as e:
                    st.error(f"Scrape failed: {e}")
                    st.session_state["scan_results"] = []

    scan_results = st.session_state.get("scan_results")
    if scan_results is not None:
        if not scan_results:
            st.info("No matching roles found. Try broader keywords or check the URL.")
        else:
            st.success(f"**{len(scan_results)}** matching role(s) found.")
            render_results(scan_results, save_key="scan_save", saved_key="scan_saved")


# ── TAB: Companies ────────────────────────────────────────────────────────────

with tab_companies:
    st.subheader("Saved Companies")
    st.caption("Companies added here are used by Run All and scheduled scans.")

    sheet = get_sheet()
    if sheet is None:
        st.warning("Google Sheets not connected — cannot manage companies.")
    else:
        companies_ws = sh.get_companies_tab(sheet)
        all_companies = sh.load_all_companies_raw(companies_ws)

        if not all_companies:
            st.info("No companies saved yet. Add one below.")
        else:
            for row_idx, co in all_companies:
                active = str(co.get("active", "TRUE")).upper() != "FALSE"
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([3, 1.5, 1, 1])
                    with c1:
                        st.markdown(f"**{co.get('name', '')}**")
                        url = co.get("url", "")
                        st.caption(url[:72] + "…" if len(url) > 72 else url)
                        if co.get("keywords"):
                            st.caption(f"🔑 {co['keywords']}")
                    with c2:
                        st.write(PLATFORM_LABELS.get(co.get("platform", "generic"), "🌐"))
                    with c3:
                        toggle_label = "✅ Active" if active else "⏸ Paused"
                        if st.button(toggle_label, key=f"toggle_{row_idx}", use_container_width=True):
                            sh.toggle_company_active(companies_ws, row_idx, not active)
                            st.rerun()
                    with c4:
                        if st.button("🗑️ Delete", key=f"del_{row_idx}", use_container_width=True):
                            sh.delete_company_row(companies_ws, row_idx)
                            st.rerun()

        st.divider()
        with st.expander("➕ Add Company", expanded=not bool(all_companies)):
            with st.form("add_company_form"):
                add_url = st.text_input("Careers page URL")
                add_name = st.text_input("Company name")
                add_keywords = st.text_input(
                    "Keywords (optional)",
                    placeholder="Engineer, Software, Data  — leave blank to use global defaults",
                )
                add_submitted = st.form_submit_button("Add Company", type="primary")
                if add_submitted:
                    add_url = add_url.strip()
                    if not add_url:
                        st.warning("URL is required.")
                    else:
                        platform = detect_platform(add_url)
                        cfg = build_company_cfg(add_url, add_name.strip() or add_url, platform)
                        cfg["keywords"] = add_keywords.strip()
                        sh.save_company(companies_ws, cfg)
                        st.success(f"Added **{cfg['name']}** ({PLATFORM_LABELS[platform]})")
                        st.rerun()


# ── TAB: Run All ──────────────────────────────────────────────────────────────

with tab_run:
    st.subheader("Scan All Companies")

    sheet = get_sheet()
    if sheet is None:
        st.warning("Google Sheets not connected.")
    else:
        companies_ws = sh.get_companies_tab(sheet)
        active_companies = sh.load_companies(companies_ws)

        if not active_companies:
            st.info("No active companies. Go to the **🏢 Companies** tab to add some.")
        else:
            st.write(f"**{len(active_companies)}** active company/companies will be scanned.")
            run_keywords = st.text_area("Keywords", value=DEFAULT_KEYWORDS, height=120, key="run_kw")

            if st.button("▶️ Scan All Companies", type="primary"):
                kws = parse_keywords(run_keywords)
                existing = sh.get_existing_urls(sheet)
                all_new: list[dict] = []

                with st.status("Scanning…", expanded=True) as status:
                    for co in active_companies:
                        st.write(f"Scanning **{co['name']}**…")
                        try:
                            results = scrape_company(co, kws, existing)
                            all_new.extend(results)
                            st.write(f"  → {len(results)} new match(es)")
                        except Exception as e:
                            st.write(f"  ⚠️ Error: {e}")
                    status.update(
                        label=f"Done — {len(all_new)} new posting(s) found",
                        state="complete",
                    )

                st.session_state["run_results"] = all_new
                st.session_state["run_saved"] = False
                st.rerun()

        run_results = st.session_state.get("run_results")
        if run_results is not None:
            st.divider()
            if not run_results:
                st.info("Nothing new since last run.")
            else:
                st.success(f"**{len(run_results)}** new posting(s) found.")
                render_results(run_results, save_key="run_save", saved_key="run_saved")


# ── TAB: Schedule ─────────────────────────────────────────────────────────────

with tab_schedule:
    st.subheader("Automated Scheduled Runs")
    st.write(
        "The tracker runs automatically via **GitHub Actions** — free, "
        "no server required. The workflow is already in your repo at "
        "`.github/workflows/scan.yml`."
    )

    st.markdown("#### Current schedule")
    st.code("0 8 * * 1-5   →   8:00 AM UTC, Monday – Friday", language="text")
    st.caption(
        "To change it, edit the `cron:` line in `.github/workflows/scan.yml`, commit, and push. "
        "You can also trigger a manual run from GitHub → Actions → Scheduled Scan → Run workflow."
    )

    st.markdown("#### One-time setup: add two GitHub secrets")
    st.markdown(
        "Go to your repo on GitHub → **Settings** → **Secrets and variables** "
        "→ **Actions** → **New repository secret** for each:"
    )
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown("**`GOOGLE_CREDENTIALS`** *(required)*")
            st.caption(
                "Paste the full contents of your `credentials.json` file "
                "(the entire JSON, starting with `{`)."
            )
    with c2:
        with st.container(border=True):
            st.markdown("**`GMAIL_APP_PASSWORD`** *(optional)*")
            st.caption(
                "Your Gmail App Password for email digests. "
                "Generate one at myaccount.google.com/apppasswords."
            )

    st.markdown("#### What each scheduled run does")
    st.info(
        "Reads your **Companies** tab → scrapes each active site → appends new matches "
        "to the **Jobs** tab → sends email digest if configured. "
        "Postings already in the sheet are never duplicated."
    )

"""Email digest — sends an HTML summary of new job postings via Gmail SMTP."""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date


def _build_html(postings: list[dict]) -> str:
    today = date.today().strftime("%B %d, %Y")
    rows = ""
    for p in postings:
        rows += (
            "<tr>"
            f"<td>{p.get('company', '')}</td>"
            f"<td><a href=\"{p.get('url', '')}\">{p.get('title', '')}</a></td>"
            f"<td>{p.get('category', '')}</td>"
            f"<td>{p.get('location', '')}</td>"
            f"<td>{p.get('posted_date', '')}</td>"
            "</tr>\n"
        )

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: Arial, sans-serif; font-size: 14px; color: #333; }}
  h2 {{ color: #1a73e8; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th {{ background: #1a73e8; color: white; padding: 8px 12px; text-align: left; }}
  td {{ padding: 7px 12px; border-bottom: 1px solid #e0e0e0; vertical-align: top; }}
  tr:hover td {{ background: #f5f9ff; }}
  a {{ color: #1a73e8; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .footer {{ margin-top: 20px; font-size: 12px; color: #888; }}
</style>
</head>
<body>
<h2>Job Tracker Digest — {today}</h2>
<p>{len(postings)} new posting(s) found matching your criteria.</p>
<table>
  <thead>
    <tr>
      <th>Company</th>
      <th>Title</th>
      <th>Category</th>
      <th>Location</th>
      <th>Posted</th>
    </tr>
  </thead>
  <tbody>
{rows}
  </tbody>
</table>
<p class="footer">Sent by job-tracker. All new postings have been logged to Google Sheets.</p>
</body>
</html>"""


def _build_plain(postings: list[dict]) -> str:
    today = date.today().strftime("%B %d, %Y")
    lines = [f"Job Tracker Digest — {today}", f"{len(postings)} new posting(s)\n"]
    for p in postings:
        lines.append(
            f"{p.get('company', '')} | {p.get('title', '')} | {p.get('location', '')}\n"
            f"  {p.get('url', '')}\n"
        )
    return "\n".join(lines)


def send_digest(postings: list[dict], email_cfg: dict) -> bool:
    """
    Send an HTML email digest for the given postings.

    Args:
        postings:   List of posting dicts to include.
        email_cfg:  The 'email' block from config.yaml.

    Returns:
        True on success, False on failure.
    """
    if not postings:
        return True

    sender = email_cfg.get("sender", "")
    recipient = email_cfg.get("recipient", "")
    smtp_host = email_cfg.get("smtp_host", "smtp.gmail.com")
    smtp_port = int(email_cfg.get("smtp_port", 587))
    password_env = email_cfg.get("smtp_password_env", "GMAIL_APP_PASSWORD")
    password = os.environ.get(password_env, "")

    if not password:
        print(f"[notifier] WARNING: env var '{password_env}' is not set — skipping email.")
        return False

    today = date.today().strftime("%Y-%m-%d")
    subject = f"Job Tracker: {len(postings)} new posting(s) — {today}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(_build_plain(postings), "plain"))
    msg.attach(MIMEText(_build_html(postings), "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, recipient, msg.as_string())
        print(f"[notifier] Digest sent to {recipient} ({len(postings)} posting(s)).")
        return True
    except smtplib.SMTPException as e:
        print(f"[notifier] ERROR sending email: {e}")
        return False

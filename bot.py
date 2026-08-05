"""
New Grad Job Bot
Checks SimplifyJobs/New-Grad-Positions for new postings and notifies via
email.

Env vars required (set as GitHub Actions secrets, see README.md):
  GMAIL_USER        - your gmail address (used as the "from")
  GMAIL_APP_PASS    - a Gmail app password (not your normal password)
  NOTIFY_EMAIL      - where to send the email digest (comma-separated for
                      multiple recipients)
"""

import json
import os
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path
from urllib.request import urlopen, Request

LISTINGS_URL = (
    "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/"
    "dev/.github/scripts/listings.json"
)
STATE_FILE = Path(__file__).parent / "last_seen.json"


def fetch_listings():
    req = Request(LISTINGS_URL, headers={"User-Agent": "newgrad-bot"})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def load_last_seen():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return 0  # first run: nothing seen yet


def save_last_seen(ts):
    STATE_FILE.write_text(json.dumps(ts))


def format_ts(ts):
    if not ts:
        return "unknown"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def format_listing(item):
    company = item.get("company_name", "Unknown company")
    title = item.get("title", "Unknown role")
    location = ", ".join(item.get("locations", [])) or "Location not listed"
    url = item.get("url", "")
    posted = format_ts(item.get("date_posted"))
    updated = format_ts(item.get("date_updated"))
    return (
        f"{company} — {title}\n"
        f"{location}\n"
        f"Posted: {posted} | Updated: {updated}\n"
        f"{url}"
    )


def parse_recipients(raw):
    return [addr.strip() for addr in raw.split(",") if addr.strip()]


def send_email(subject, body, to_addrs, gmail_user, gmail_pass):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = ", ".join(to_addrs)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
        server.login(gmail_user, gmail_pass)
        server.sendmail(gmail_user, to_addrs, msg.as_string())


def main():
    gmail_user = os.environ["GMAIL_USER"]
    gmail_pass = os.environ["GMAIL_APP_PWD"]
    notify_emails = parse_recipients(os.environ["NOTIFY_EMAIL"])

    listings = fetch_listings()
    last_seen_ts = load_last_seen()

    new_items = [
        item
        for item in listings
        if item.get("active") and item.get("date_posted", 0) > last_seen_ts
    ]

    if not new_items:
        print("No new postings.")
        return

    # newest first (every item here already passed the date_posted filter above)
    new_items.sort(key=lambda i: i["date_posted"], reverse=True)
    newest_ts = new_items[0]["date_posted"]

    body = "\n\n".join(format_listing(i) for i in new_items)
    subject = f"{len(new_items)} new grad posting(s)"
    send_email(
        subject=subject,
        body=body,
        to_addrs=notify_emails,
        gmail_user=gmail_user,
        gmail_pass=gmail_pass,
    )
    print(f"Emailed {len(new_items)} new postings to {', '.join(notify_emails)}")

    save_last_seen(newest_ts)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Poll GitHub notifications, store in SQLite, fire notify-send for new ones."""

import datetime
import json
import sqlite3
import subprocess
import sys
import time

import db

POLL_SECONDS = 60

# https://docs.github.com/en/rest/activity/notifications#about-notification-reasons
ALLOWED_REASONS = {
    "mention",
    "team_mention",
    "review_requested",
    "assign",
    "author",
    "comment",
}


def fetch_notifications() -> list[dict]:
    result = subprocess.run(
        ["gh", "api", "/notifications"],
        capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


def html_url(subject: dict, repo: str) -> str:
    api_url = subject.get("url") or ""
    number = api_url.rsplit("/", 1)[-1] if api_url else ""
    stype = subject.get("type")
    if stype == "PullRequest" and number:
        return f"https://github.com/{repo}/pull/{number}"
    if stype == "Issue" and number:
        return f"https://github.com/{repo}/issues/{number}"
    if stype == "Discussion" and number:
        return f"https://github.com/{repo}/discussions/{number}"
    if stype == "Commit" and number:
        return f"https://github.com/{repo}/commit/{number}"
    return f"https://github.com/{repo}"


def fire_popup(reason: str, repo: str, title: str, url: str) -> None:
    summary = f"[{reason}] {repo}"
    body = f"{title}\n{url}"
    subprocess.run(
        ["notify-send", "--app-name=gh-notify", summary, body],
        check=False,
    )
    print(f"{summary} :: {title} :: {url}", flush=True)


def upsert(conn: sqlite3.Connection, n: dict, *, popup: bool) -> None:
    nid = n["id"]
    reason = n["reason"]
    repo = n["repository"]["full_name"]
    subject = n["subject"]
    title = subject["title"]
    url = html_url(subject, repo)
    updated_at = n["updated_at"]
    seen_at = datetime.datetime.now(datetime.UTC).isoformat()
    row = conn.execute(
        "SELECT updated_at FROM notifications WHERE id = ?", (nid,)
    ).fetchone()
    if row is None:
        conn.execute(
            """INSERT INTO notifications
                 (id, reason, repo, subject_type, title, url, updated_at, seen_at, state)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'unread')""",
            (nid, reason, repo, subject.get("type"), title, url, updated_at, seen_at),
        )
        is_new = True
    elif row[0] < updated_at:
        conn.execute(
            """UPDATE notifications
                 SET reason=?, title=?, url=?, updated_at=?, state='unread'
                 WHERE id=?""",
            (reason, title, url, updated_at, nid),
        )
        is_new = True
    else:
        is_new = False
    conn.commit()
    if is_new and popup:
        fire_popup(reason, repo, title, url)


def tick(conn: sqlite3.Connection) -> None:
    try:
        notifications = fetch_notifications()
    except subprocess.CalledProcessError as e:
        print(f"gh api failed: {e.stderr.strip()}", file=sys.stderr, flush=True)
        return
    for n in notifications:
        if n["reason"] not in ALLOWED_REASONS:
            continue
        upsert(conn, n, popup=True)


def main() -> None:
    conn = db.connect()
    fresh = conn.execute("SELECT 1 FROM notifications LIMIT 1").fetchone() is None
    if fresh:
        # First run: record current inbox as unread but skip popups, so the daemon
        # doesn't flood at startup while still seeding the UI with the backlog.
        for n in fetch_notifications():
            if n["reason"] in ALLOWED_REASONS:
                upsert(conn, n, popup=False)
        print("Primed initial notifications. Watching...", flush=True)
    while True:
        tick(conn)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Minimal Flask UI for gh-notify."""

import hashlib
from datetime import datetime, timezone

from flask import Flask, g, jsonify, redirect, render_template, request, url_for

import db

app = Flask(__name__)


def state_sig(conn, view: str) -> str:
    """Fingerprint of the rows shown in a given view. Changes iff list changes."""
    rows = conn.execute(
        "SELECT id, updated_at FROM notifications WHERE state=? ORDER BY id",
        (view,),
    ).fetchall()
    payload = "|".join(f"{r['id']}:{r['updated_at']}" for r in rows)
    return hashlib.sha1(payload.encode()).hexdigest()[:16]


@app.template_filter("humantime")
def humantime(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso
    seconds = int((datetime.now(timezone.utc) - dt).total_seconds())
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    if seconds < 86400 * 7:
        return f"{seconds // 86400}d ago"
    return dt.strftime("%b %d")


def get_conn():
    if "conn" not in g:
        g.conn = db.connect()
    return g.conn


@app.teardown_appcontext
def close_conn(exception):
    conn = g.pop("conn", None)
    if conn is not None:
        conn.close()


@app.context_processor
def inject_counts():
    conn = get_conn()
    unread = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE state='unread'"
    ).fetchone()[0]
    return {"unread_count": unread}


@app.route("/")
def index():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM notifications WHERE state='unread' ORDER BY updated_at DESC"
    ).fetchall()
    return render_template("index.html", rows=rows, view="unread", sig=state_sig(conn, "unread"))


@app.route("/read")
def read():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM notifications WHERE state='read' ORDER BY updated_at DESC LIMIT 100"
    ).fetchall()
    return render_template("index.html", rows=rows, view="read", sig=state_sig(conn, "read"))


@app.route("/api/state")
def api_state():
    view = request.args.get("view", "unread")
    if view not in {"unread", "read"}:
        return jsonify(error="bad view"), 400
    return jsonify(sig=state_sig(get_conn(), view))


@app.post("/mark/<state>/<nid>")
def mark(state: str, nid: str):
    if state not in {"read", "unread"}:
        return "bad state", 400
    conn = get_conn()
    conn.execute("UPDATE notifications SET state=? WHERE id=?", (state, nid))
    conn.commit()
    return redirect(request.referrer or url_for("index"))


@app.post("/mark-all-read")
def mark_all_read():
    conn = get_conn()
    conn.execute("UPDATE notifications SET state='read' WHERE state='unread'")
    conn.commit()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)

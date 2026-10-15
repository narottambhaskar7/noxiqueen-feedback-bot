import os
import sqlite3
from datetime import datetime, timedelta, timezone
from io import BytesIO
from openpyxl import Workbook

DB_PATH = os.getenv("DB_PATH", "noxiqueen.sqlite3")


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def init_db():
    with connect() as c:
        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            full_name TEXT DEFAULT '',
            channel TEXT DEFAULT '',
            auto_post INTEGER DEFAULT 0,
            auto_delete INTEGER DEFAULT 1,
            delete_hours INTEGER DEFAULT 24,
            joined_at TEXT NOT NULL
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            feedback TEXT NOT NULL,
            photo_ids TEXT NOT NULL,
            photo_count INTEGER NOT NULL,
            mode TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            channel TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_feedback_user ON feedback(user_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_feedback_expiry ON feedback(expires_at)")


def get_user(user_id, username="", full_name=""):
    with connect() as c:
        row = c.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if row:
            c.execute("UPDATE users SET username=?, full_name=? WHERE user_id=?",
                      (username or row["username"], full_name or row["full_name"], user_id))
            row = c.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
            return dict(row)
        c.execute("""INSERT INTO users(user_id, username, full_name, joined_at)
                     VALUES(?,?,?,?)""", (user_id, username, full_name, now_iso()))
        row = c.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        return dict(row)


def set_user_channel(user_id, channel):
    with connect() as c:
        c.execute("UPDATE users SET channel=? WHERE user_id=?", (channel, user_id))


def set_user_setting(user_id, setting, value):
    allowed = {"auto_post", "auto_delete", "delete_hours"}
    if setting not in allowed:
        raise ValueError("Invalid setting")
    with connect() as c:
        c.execute(f"UPDATE users SET {setting}=? WHERE user_id=?", (value, user_id))


def create_feedback(user_id, feedback, photo_count, mode):
    user = get_user(user_id)
    created = datetime.now(timezone.utc)
    expires = created + timedelta(hours=int(user["delete_hours"]))
    with connect() as c:
        cur = c.execute("""INSERT INTO feedback
            (user_id, feedback, photo_ids, photo_count, mode, status, created_at, expires_at)
            VALUES(?,?,?,?,?,?,?,?)""",
            (user_id, feedback, "", photo_count, mode, "PENDING", created.isoformat(), expires.isoformat()))
        return cur.lastrowid


def update_feedback_status(feedback_id, status, channel=""):
    with connect() as c:
        c.execute("UPDATE feedback SET status=?, channel=? WHERE id=?", (status, channel, feedback_id))


def add_feedback_photo(feedback_id, photo_id):
    pass


def get_feedback(feedback_id, user_id=None):
    with connect() as c:
        if user_id is None:
            row = c.execute("SELECT * FROM feedback WHERE id=?", (feedback_id,)).fetchone()
        else:
            row = c.execute("SELECT * FROM feedback WHERE id=? AND user_id=?", (feedback_id, user_id)).fetchone()
        return dict(row) if row else None


def list_feedback(user_id, limit=10):
    with connect() as c:
        rows = c.execute("""SELECT id, created_at, status, photo_count FROM feedback
                            WHERE user_id=? ORDER BY id DESC LIMIT ?""", (user_id, limit)).fetchall()
        return [dict(r) for r in rows]


def delete_feedback(feedback_id, user_id):
    with connect() as c:
        cur = c.execute("DELETE FROM feedback WHERE id=? AND user_id=?", (feedback_id, user_id))
        return cur.rowcount > 0


def delete_expired(uid=None, force_hours=None):
    now = datetime.now(timezone.utc)
    with connect() as c:
        if uid is not None and force_hours is not None:
            cutoff = (now - timedelta(hours=force_hours)).isoformat()
            cur = c.execute("DELETE FROM feedback WHERE user_id=? AND created_at<=?", (uid, cutoff))
        else:
            # Expire records only when that user currently has Auto Delete enabled.
            cur = c.execute("""DELETE FROM feedback WHERE expires_at<=? AND user_id IN
                (SELECT user_id FROM users WHERE auto_delete=1)""", (now.isoformat(),))
        return cur.rowcount


def export_user_excel(user_id=None):
    with connect() as c:
        if user_id is None:
            rows = c.execute("""SELECT f.*, u.username, u.full_name FROM feedback f
                                LEFT JOIN users u ON f.user_id=u.user_id ORDER BY f.id DESC""").fetchall()
        else:
            rows = c.execute("SELECT * FROM feedback WHERE user_id=? ORDER BY id DESC", (user_id,)).fetchall()
    if not rows:
        return None
    wb = Workbook()
    ws = wb.active
    ws.title = "Feedback"
    ws.append(["Feedback ID", "User ID", "Username", "Name", "Created At", "Feedback",
               "Photo Count", "Mode", "Status", "Channel", "Expires At"])
    for r in rows:
        d = dict(r)
        ws.append([
            d["id"], d["user_id"], d.get("username", ""), d.get("full_name", ""),
            d["created_at"], d["feedback"], d["photo_count"], d["mode"],
            d["status"], d["channel"], d["expires_at"]
        ])
    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio


def count_stats():
    with connect() as c:
        users = c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
        feedback = c.execute("SELECT COUNT(*) n FROM feedback").fetchone()["n"]
        posted = c.execute("SELECT COUNT(*) n FROM feedback WHERE status='POSTED'").fetchone()["n"]
        other = feedback - posted
    return {"users": users, "feedback": feedback, "posted": posted, "other": other}


def list_user_ids():
    with connect() as c:
        return [r["user_id"] for r in c.execute("SELECT user_id FROM users").fetchall()]

"""One SQLite file for the household: approvals (human taps), jobs (calls and tasks that run later),
facts (memory shared by all Experts) and events (the journey timeline shown in the demo)."""
import json
import sqlite3
import threading
import time
import uuid

SCHEMA = """
CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY, expert TEXT, card TEXT, status TEXT,
    choice TEXT, result TEXT, created REAL, updated REAL);
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, expert TEXT, kind TEXT, person TEXT,
    payload TEXT, run_at REAL, status TEXT, result TEXT, created REAL);
CREATE TABLE IF NOT EXISTS facts(person TEXT, key TEXT, value TEXT, source TEXT, updated REAL,
    PRIMARY KEY (person, key));
CREATE TABLE IF NOT EXISTS events(ts REAL, expert TEXT, ref TEXT, what TEXT);
CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY, store TEXT, card TEXT, ref TEXT, items TEXT, total TEXT,
    address TEXT, address_id TEXT, status TEXT, eta TEXT, detail TEXT, placed REAL, updated REAL, delivered REAL);
"""


def _new_id():
    return uuid.uuid4().hex[:10]


class _Rows:
    """A finished statement: rows fetched while the lock was held (cursors are not shared across threads)."""

    def __init__(self, cur):
        self.rowcount = cur.rowcount
        self.rows = cur.fetchall()

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows

    def __iter__(self):
        return iter(self.rows)


class _LockedDB:
    """One SQLite connection used from FastAPI's thread pool and the event loop: one statement at a time."""

    def __init__(self, conn):
        self.conn, self.lock = conn, threading.RLock()

    def execute(self, query, args=()):
        with self.lock:
            return _Rows(self.conn.execute(query, args))

    def executescript(self, script):
        with self.lock:
            self.conn.executescript(script)


class Store:
    def __init__(self, path="quickpick.db"):
        conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        conn.row_factory = sqlite3.Row
        self.db = _LockedDB(conn)
        self.db.executescript(SCHEMA)

    # ---- events: what happened, when (the demo timeline) ----
    def log(self, expert, ref, what):
        self.db.execute("INSERT INTO events VALUES (?,?,?,?)", (time.time(), expert, ref, what))

    def timeline(self, ref=None, limit=50):
        q, args = "SELECT * FROM events", []
        if ref:
            q, args = q + " WHERE ref=?", [ref]
        return [dict(r) for r in self.db.execute(q + " ORDER BY ts DESC LIMIT ?", args + [limit])]

    # ---- approvals: nothing is committed without a human tap ----
    def add_card(self, card):
        aid, now = _new_id(), time.time()
        self.db.execute("INSERT INTO approvals VALUES (?,?,?,?,?,?,?,?)",
                        (aid, card["expert"], json.dumps(card), "waiting", None, None, now, now))
        self.log(card["expert"], aid, f"card: {card['title']}")
        return aid

    def claim(self, aid, choice):
        """waiting -> running exactly once; a second tap gets None (double-tap guard)."""
        cur = self.db.execute("UPDATE approvals SET status='running', choice=?, updated=? "
                              "WHERE id=? AND status='waiting'", (choice, time.time(), aid))
        if cur.rowcount != 1:
            return None
        self.log("approvals", aid, f"tapped: {choice}")
        return json.loads(self.db.execute("SELECT card FROM approvals WHERE id=?", (aid,)).fetchone()[0])

    def finish(self, aid, ok, result):
        """running -> done | failed. A failed card never returns to waiting: no silent retries."""
        self.db.execute("UPDATE approvals SET status=?, result=?, updated=? WHERE id=? AND status='running'",
                        ("done" if ok else "failed", json.dumps(result, default=str), time.time(), aid))
        self.log("approvals", aid, "done" if ok else f"failed: {result}")

    def reject(self, aid):
        return self.db.execute("UPDATE approvals SET status='rejected', updated=? WHERE id=? AND status='waiting'",
                               (time.time(), aid)).rowcount == 1

    def card(self, aid):
        r = self.db.execute("SELECT * FROM approvals WHERE id=?", (aid,)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["card"] = json.loads(d["card"])
        d["result"] = json.loads(d["result"]) if d["result"] else None
        return d

    def cards(self, status="waiting"):
        rows = self.db.execute("SELECT id FROM approvals WHERE status=? ORDER BY created DESC", (status,)).fetchall()
        return [self.card(r["id"]) for r in rows]

    def recent_cards(self, limit=8):
        """Cards a human already acted on (running, done, failed, rejected), newest first."""
        rows = self.db.execute("SELECT id FROM approvals WHERE status!='waiting' ORDER BY updated DESC LIMIT ?",
                               (limit,)).fetchall()
        return [self.card(r["id"]) for r in rows]

    def note(self, aid, result):
        """Save an interim result on a running card (e.g. UPI waiting for payment). Status is unchanged."""
        self.db.execute("UPDATE approvals SET result=?, updated=? WHERE id=? AND status='running'",
                        (json.dumps(result, default=str), time.time(), aid))

    # ---- jobs: calls and tasks that run later ----
    def add_job(self, expert, kind, person, payload, run_at=None):
        jid = _new_id()
        self.db.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?)",
                        (jid, expert, kind, person, json.dumps(payload),
                         time.time() if run_at is None else run_at, "scheduled", None, time.time()))
        self.log(expert, jid, f"scheduled {kind} for {person}")
        return jid

    def job(self, jid):
        r = self.db.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
        if not r:
            return None
        return dict(r, payload=json.loads(r["payload"]), result=json.loads(r["result"]) if r["result"] else None)

    def due(self, now=None):
        now = time.time() if now is None else now
        rows = self.db.execute("SELECT id FROM jobs WHERE status='scheduled' AND run_at<=? ORDER BY run_at",
                               (now,)).fetchall()
        return [self.job(r["id"]) for r in rows]

    def upcoming(self):
        rows = self.db.execute("SELECT id FROM jobs WHERE status='scheduled' ORDER BY run_at").fetchall()
        return [self.job(r["id"]) for r in rows]

    def start_job(self, jid):
        return self.db.execute("UPDATE jobs SET status='running' WHERE id=? AND status='scheduled'",
                               (jid,)).rowcount == 1

    def end_job(self, jid, ok, result=None):
        self.db.execute("UPDATE jobs SET status=?, result=? WHERE id=?",
                        ("done" if ok else "failed", json.dumps(result, default=str), jid))

    def run_now(self, jid):
        """Demo button: a scheduled job becomes due immediately."""
        return self.db.execute("UPDATE jobs SET run_at=? WHERE id=? AND status='scheduled'",
                               (time.time(), jid)).rowcount == 1

    def recent_jobs(self, since):
        """Jobs that already ran since a timestamp (calls ringing or finished), newest first."""
        rows = self.db.execute("SELECT id FROM jobs WHERE status!='scheduled' AND run_at>=? ORDER BY run_at DESC",
                               (since,)).fetchall()
        return [self.job(r["id"]) for r in rows]

    # ---- orders: what was actually placed, and where it is now ----
    def add_order(self, oid, store, card, ref, items, total, address, address_id, status="placed", eta=None):
        now = time.time()
        self.db.execute("INSERT OR IGNORE INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (str(oid), store, card, ref, json.dumps(items), total, address, address_id, status, eta,
                         None, now, now, None))
        self.log("orders", str(oid), f"{store} order placed ({total})")

    def update_order(self, oid, status=None, eta=None, detail=None, delivered=False):
        """Returns True when the status changed (the tracker logs it on the timeline)."""
        old = self.order(oid)
        if not old:
            return False
        self.db.execute("UPDATE orders SET status=COALESCE(?, status), eta=COALESCE(?, eta), "
                        "detail=COALESCE(?, detail), updated=?, delivered=COALESCE(delivered, ?) WHERE id=?",
                        (status, eta, json.dumps(detail, default=str) if detail is not None else None, time.time(),
                         time.time() if delivered else None, str(oid)))
        return bool(status) and status != old["status"]

    def order(self, oid):
        r = self.db.execute("SELECT * FROM orders WHERE id=?", (str(oid),)).fetchone()
        if not r:
            return None
        return dict(r, items=json.loads(r["items"] or "[]"), detail=json.loads(r["detail"]) if r["detail"] else None)

    def orders(self, active=False, limit=20):
        q = "SELECT id FROM orders" + (" WHERE delivered IS NULL AND store != 'dry run'" if active else "")
        rows = self.db.execute(q + " ORDER BY placed DESC LIMIT ?", (limit,)).fetchall()
        return [self.order(r["id"]) for r in rows]

    # ---- facts: household memory shared by all Experts ----
    def remember(self, person, key, value, source):
        self.db.execute("INSERT INTO facts VALUES (?,?,?,?,?) ON CONFLICT(person, key) DO UPDATE SET "
                        "value=excluded.value, source=excluded.source, updated=excluded.updated",
                        (person, key, json.dumps(value, default=str), source, time.time()))

    def facts(self, person=None, prefix=""):
        q, args = "SELECT * FROM facts WHERE key LIKE ?", [prefix + "%"]
        if person:
            q, args = q + " AND person=?", args + [person]
        return [dict(r, value=json.loads(r["value"])) for r in self.db.execute(q + " ORDER BY updated", args)]

    def forget(self, person, key):
        return self.db.execute("DELETE FROM facts WHERE person=? AND key=?", (person, key)).rowcount == 1

    def cancel(self, jid):
        """A scheduled job that should not run any more (e.g. the daily call was switched off)."""
        ok = self.db.execute("UPDATE jobs SET status='cancelled' WHERE id=? AND status='scheduled'", (jid,)).rowcount == 1
        if ok:
            self.log("jobs", jid, "cancelled")
        return ok

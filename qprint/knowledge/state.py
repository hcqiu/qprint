"""Small session state, separate from the read-only mathematical index.

DELETE journaling avoids WAL/shared-memory writes on query connections.
Each write is a short SQLite transaction; readers never create files.
"""
import sqlite3
import time

from ..paths import safe_path


class NavigationState:
    def __init__(self, root, session):
        self.path = safe_path(root, ".qprint/state/navigation.sqlite")
        self.session = session

    def read(self):
        if not self.path.exists():
            return {"focus": None, "recent": []}
        db = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            db.execute("BEGIN")
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"focus", "recent"} <= tables:
                return {"focus": None, "recent": []}
            focus = db.execute("SELECT * FROM focus WHERE session=?", (self.session,)).fetchone()
            recent = db.execute("SELECT node_id,touched FROM recent WHERE session=? ORDER BY touched DESC,node_id", (self.session,))
            return {"focus": dict(focus) if focus else None, "recent": [dict(r) for r in recent]}
        finally:
            db.close()

    def write(self, node, *, focus=False, view="rendered", selection="", origin="host", document=None):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=30)
        try:
            # No journal-mode changes on existing connections, no WAL sidecars.
            with db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("CREATE TABLE IF NOT EXISTS recent (session TEXT, node_id TEXT, touched INTEGER, PRIMARY KEY(session,node_id))")
                db.execute("CREATE TABLE IF NOT EXISTS focus (session TEXT PRIMARY KEY, node_id TEXT, view TEXT, selection TEXT, origin TEXT, updated INTEGER)")
                if "document" not in {r[1] for r in db.execute("PRAGMA table_info(focus)")}:
                    db.execute("ALTER TABLE focus ADD COLUMN document TEXT")
                now = time.time_ns()
                if node is not None:
                    db.execute("INSERT OR REPLACE INTO recent VALUES(?,?,?)", (self.session, node, now))
                    db.execute("DELETE FROM recent WHERE session=? AND node_id NOT IN (SELECT node_id FROM recent WHERE session=? ORDER BY touched DESC,node_id LIMIT 32)", (self.session, self.session))
                if focus:
                    db.execute("INSERT OR REPLACE INTO focus VALUES(?,?,?,?,?,?,?)", (self.session, node, view, selection, origin, now, document))
        finally:
            db.close()

"""SQLite storage layer for Diwan."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Optional

from .models import (
    Comment,
    Link,
    LinkRelation,
    Priority,
    Sprint,
    SprintStatus,
    Status,
    Ticket,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    description TEXT DEFAULT '',
    status      TEXT DEFAULT 'backlog',
    priority    TEXT DEFAULT 'medium',
    labels      TEXT DEFAULT '[]',
    assignee    TEXT DEFAULT '',
    sprint_id   TEXT,
    parent_id   TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS comments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id   TEXT NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    author      TEXT DEFAULT '',
    content     TEXT NOT NULL,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sprints (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    status      TEXT DEFAULT 'planning',
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS links (
    from_id     TEXT NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    to_id       TEXT NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    relation    TEXT NOT NULL,
    PRIMARY KEY (from_id, to_id, relation)
);

CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_sprint ON tickets(sprint_id);
CREATE INDEX IF NOT EXISTS idx_tickets_parent ON tickets(parent_id);
CREATE INDEX IF NOT EXISTS idx_comments_ticket ON comments(ticket_id);
CREATE INDEX IF NOT EXISTS idx_links_from ON links(from_id);
CREATE INDEX IF NOT EXISTS idx_links_to ON links(to_id);
"""

# Inverse relations for bidirectional link creation
_INVERSE = {
    LinkRelation.BLOCKS: LinkRelation.BLOCKED_BY,
    LinkRelation.BLOCKED_BY: LinkRelation.BLOCKS,
    LinkRelation.PARENT_OF: LinkRelation.CHILD_OF,
    LinkRelation.CHILD_OF: LinkRelation.PARENT_OF,
    LinkRelation.RELATES_TO: LinkRelation.RELATES_TO,
}


def default_db_path() -> Path:
    """Return the default database path for the current directory project."""
    return Path.cwd() / ".diwan" / "diwan.db"


class DiwanDB:
    """SQLite-backed storage for tickets, comments, sprints, and links."""

    def __init__(self, db_path: Optional[str | Path] = None):
        self.db_path = Path(db_path) if db_path else default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def init(self) -> None:
        """Create tables if they don't exist."""
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── ID generation ──

    def _next_ticket_id(self) -> str:
        row = self.conn.execute(
            "SELECT id FROM tickets ORDER BY CAST(SUBSTR(id, 3) AS INTEGER) DESC LIMIT 1"
        ).fetchone()
        if not row:
            return "T-001"
        num = int(row["id"].split("-", 1)[1]) + 1
        return f"T-{num:03d}"

    def _next_sprint_id(self) -> str:
        row = self.conn.execute(
            "SELECT id FROM sprints ORDER BY CAST(SUBSTR(id, 8) AS INTEGER) DESC LIMIT 1"
        ).fetchone()
        if not row:
            return "sprint-1"
        num = int(row["id"].split("-", 1)[1]) + 1
        return f"sprint-{num}"

    # ── Tickets ──

    def create_ticket(
        self,
        title: str,
        description: str = "",
        status: str = "backlog",
        priority: str = "medium",
        labels: Optional[list[str]] = None,
        assignee: str = "",
        sprint_id: Optional[str] = None,
        parent_id: Optional[str] = None,
    ) -> Ticket:
        tid = self._next_ticket_id()
        Status(status)  # validate
        Priority(priority)  # validate
        labels_json = json.dumps(labels or [])
        self.conn.execute(
            """INSERT INTO tickets (id, title, description, status, priority, labels, assignee, sprint_id, parent_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (tid, title, description, status, priority, labels_json, assignee, sprint_id, parent_id),
        )
        self.conn.commit()
        return self.get_ticket(tid)  # type: ignore[return-value]

    def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        row = self.conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if not row:
            return None
        return Ticket.from_row(dict(row))

    def update_ticket(self, ticket_id: str, **fields) -> Optional[Ticket]:
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return None

        allowed = {"title", "description", "status", "priority", "labels", "assignee", "sprint_id", "parent_id"}
        updates = {}
        for k, v in fields.items():
            if k not in allowed:
                continue
            if k == "status":
                Status(v)  # validate
            elif k == "priority":
                Priority(v)  # validate
            elif k == "labels":
                v = json.dumps(v) if isinstance(v, list) else v
            updates[k] = v

        if not updates:
            return ticket

        updates["updated_at"] = "datetime('now')"
        set_clause = ", ".join(
            f"{k} = datetime('now')" if k == "updated_at" else f"{k} = ?"
            for k in updates
        )
        values = [v for k, v in updates.items() if k != "updated_at"]
        values.append(ticket_id)

        self.conn.execute(
            f"UPDATE tickets SET {set_clause} WHERE id = ?",
            values,
        )
        self.conn.commit()
        return self.get_ticket(ticket_id)

    def delete_ticket(self, ticket_id: str) -> bool:
        cur = self.conn.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def list_tickets(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        sprint_id: Optional[str] = None,
        assignee: Optional[str] = None,
        labels: Optional[list[str]] = None,
        parent_id: Optional[str] = None,
    ) -> list[Ticket]:
        query = "SELECT * FROM tickets WHERE 1=1"
        params: list = []

        if status:
            query += " AND status = ?"
            params.append(status)
        if priority:
            query += " AND priority = ?"
            params.append(priority)
        if sprint_id:
            query += " AND sprint_id = ?"
            params.append(sprint_id)
        if assignee:
            query += " AND assignee = ?"
            params.append(assignee)
        if parent_id:
            query += " AND parent_id = ?"
            params.append(parent_id)

        query += " ORDER BY CAST(SUBSTR(id, 3) AS INTEGER)"
        rows = self.conn.execute(query, params).fetchall()
        tickets = [Ticket.from_row(dict(r)) for r in rows]

        if labels:
            tickets = [
                t for t in tickets
                if any(lbl in t.labels for lbl in labels)
            ]

        return tickets

    def search_tickets(self, query: str) -> list[Ticket]:
        rows = self.conn.execute(
            "SELECT * FROM tickets WHERE title LIKE ? OR description LIKE ? ORDER BY CAST(SUBSTR(id, 3) AS INTEGER)",
            (f"%{query}%", f"%{query}%"),
        ).fetchall()
        return [Ticket.from_row(dict(r)) for r in rows]

    def bulk_update(self, ticket_ids: list[str], **fields) -> list[Ticket]:
        results = []
        for tid in ticket_ids:
            t = self.update_ticket(tid, **fields)
            if t:
                results.append(t)
        return results

    # ── Comments ──

    def add_comment(self, ticket_id: str, content: str, author: str = "") -> Optional[Comment]:
        if not self.get_ticket(ticket_id):
            return None
        cur = self.conn.execute(
            "INSERT INTO comments (ticket_id, author, content) VALUES (?, ?, ?)",
            (ticket_id, author, content),
        )
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM comments WHERE id = ?", (cur.lastrowid,)).fetchone()
        return Comment.from_row(dict(row))

    def list_comments(self, ticket_id: str) -> list[Comment]:
        rows = self.conn.execute(
            "SELECT * FROM comments WHERE ticket_id = ? ORDER BY created_at", (ticket_id,)
        ).fetchall()
        return [Comment.from_row(dict(r)) for r in rows]

    # ── Sprints ──

    def create_sprint(self, name: str, status: str = "planning") -> Sprint:
        sid = self._next_sprint_id()
        SprintStatus(status)  # validate
        self.conn.execute(
            "INSERT INTO sprints (id, name, status) VALUES (?, ?, ?)",
            (sid, name, status),
        )
        self.conn.commit()
        return self.get_sprint(sid)  # type: ignore[return-value]

    def get_sprint(self, sprint_id: str) -> Optional[Sprint]:
        row = self.conn.execute("SELECT * FROM sprints WHERE id = ?", (sprint_id,)).fetchone()
        if not row:
            return None
        return Sprint.from_row(dict(row))

    def list_sprints(self) -> list[Sprint]:
        rows = self.conn.execute("SELECT * FROM sprints ORDER BY created_at").fetchall()
        return [Sprint.from_row(dict(r)) for r in rows]

    def update_sprint(self, sprint_id: str, **fields) -> Optional[Sprint]:
        sprint = self.get_sprint(sprint_id)
        if not sprint:
            return None
        allowed = {"name", "status"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if "status" in updates:
            SprintStatus(updates["status"])
        if not updates:
            return sprint
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [sprint_id]
        self.conn.execute(f"UPDATE sprints SET {set_clause} WHERE id = ?", values)
        self.conn.commit()
        return self.get_sprint(sprint_id)

    def add_to_sprint(self, sprint_id: str, ticket_ids: list[str]) -> list[Ticket]:
        if not self.get_sprint(sprint_id):
            return []
        results = []
        for tid in ticket_ids:
            t = self.update_ticket(tid, sprint_id=sprint_id)
            if t:
                results.append(t)
        return results

    def remove_from_sprint(self, ticket_id: str) -> Optional[Ticket]:
        return self.update_ticket(ticket_id, sprint_id=None)

    # ── Links ──

    def link_tickets(self, from_id: str, to_id: str, relation: str) -> Optional[Link]:
        rel = LinkRelation(relation)
        if not self.get_ticket(from_id) or not self.get_ticket(to_id):
            return None
        # Create bidirectional link
        inv = _INVERSE[rel]
        try:
            self.conn.execute(
                "INSERT OR IGNORE INTO links (from_id, to_id, relation) VALUES (?, ?, ?)",
                (from_id, to_id, rel.value),
            )
            self.conn.execute(
                "INSERT OR IGNORE INTO links (from_id, to_id, relation) VALUES (?, ?, ?)",
                (to_id, from_id, inv.value),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            return None
        return Link(from_id=from_id, to_id=to_id, relation=rel)

    def unlink_tickets(self, from_id: str, to_id: str, relation: str) -> bool:
        rel = LinkRelation(relation)
        inv = _INVERSE[rel]
        cur = self.conn.execute(
            "DELETE FROM links WHERE from_id = ? AND to_id = ? AND relation = ?",
            (from_id, to_id, rel.value),
        )
        self.conn.execute(
            "DELETE FROM links WHERE from_id = ? AND to_id = ? AND relation = ?",
            (to_id, from_id, inv.value),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def get_links(self, ticket_id: str) -> list[Link]:
        rows = self.conn.execute(
            "SELECT * FROM links WHERE from_id = ?", (ticket_id,)
        ).fetchall()
        return [Link.from_row(dict(r)) for r in rows]

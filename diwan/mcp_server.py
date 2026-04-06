"""Diwan MCP server — stdio transport for agent access."""

from __future__ import annotations

import os
from typing import Optional

from mcp.server.fastmcp import FastMCP

from .db import DiwanDB

mcp = FastMCP("diwan", instructions="Diwan issue tracker. Manage tickets, sprints, comments, and dependencies.")

_db: Optional[DiwanDB] = None


def _get_db() -> DiwanDB:
    global _db
    if _db is None:
        db_path = os.environ.get("DIWAN_DB")
        _db = DiwanDB(db_path) if db_path else DiwanDB()
        _db.init()
    return _db


# ── Tickets ──


@mcp.tool()
def create_ticket(
    title: str,
    description: str = "",
    status: str = "backlog",
    priority: str = "medium",
    labels: Optional[list[str]] = None,
    assignee: str = "",
    sprint_id: Optional[str] = None,
    parent_id: Optional[str] = None,
) -> dict:
    """Create a new ticket. Returns the created ticket."""
    db = _get_db()
    t = db.create_ticket(
        title=title,
        description=description,
        status=status,
        priority=priority,
        labels=labels,
        assignee=assignee,
        sprint_id=sprint_id,
        parent_id=parent_id,
    )
    return t.to_dict()


@mcp.tool()
def update_ticket(
    ticket_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    labels: Optional[list[str]] = None,
    assignee: Optional[str] = None,
    sprint_id: Optional[str] = None,
    parent_id: Optional[str] = None,
) -> dict:
    """Update fields on an existing ticket. Only provided fields are changed."""
    db = _get_db()
    fields = {}
    if title is not None:
        fields["title"] = title
    if description is not None:
        fields["description"] = description
    if status is not None:
        fields["status"] = status
    if priority is not None:
        fields["priority"] = priority
    if labels is not None:
        fields["labels"] = labels
    if assignee is not None:
        fields["assignee"] = assignee
    if sprint_id is not None:
        fields["sprint_id"] = sprint_id
    if parent_id is not None:
        fields["parent_id"] = parent_id

    t = db.update_ticket(ticket_id, **fields)
    if not t:
        return {"error": f"Ticket {ticket_id} not found"}
    return t.to_dict()


@mcp.tool()
def get_ticket(ticket_id: str) -> dict:
    """Get full details of a ticket by ID, including its links."""
    db = _get_db()
    t = db.get_ticket(ticket_id)
    if not t:
        return {"error": f"Ticket {ticket_id} not found"}
    result = t.to_dict()
    result["links"] = [lnk.to_dict() for lnk in db.get_links(ticket_id)]
    result["comments"] = [c.to_dict() for c in db.list_comments(ticket_id)]
    return result


@mcp.tool()
def list_tickets(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    sprint_id: Optional[str] = None,
    assignee: Optional[str] = None,
    labels: Optional[list[str]] = None,
    parent_id: Optional[str] = None,
) -> list[dict]:
    """List tickets with optional filters."""
    db = _get_db()
    tickets = db.list_tickets(
        status=status,
        priority=priority,
        sprint_id=sprint_id,
        assignee=assignee,
        labels=labels,
        parent_id=parent_id,
    )
    return [t.to_dict() for t in tickets]


@mcp.tool()
def search_tickets(query: str) -> list[dict]:
    """Search tickets by text in title or description."""
    db = _get_db()
    tickets = db.search_tickets(query)
    return [t.to_dict() for t in tickets]


@mcp.tool()
def delete_ticket(ticket_id: str) -> dict:
    """Delete a ticket by ID."""
    db = _get_db()
    ok = db.delete_ticket(ticket_id)
    if not ok:
        return {"error": f"Ticket {ticket_id} not found"}
    return {"deleted": ticket_id}


# ── Comments ──


@mcp.tool()
def add_comment(ticket_id: str, content: str, author: str = "") -> dict:
    """Add a comment to a ticket."""
    db = _get_db()
    c = db.add_comment(ticket_id, content, author)
    if not c:
        return {"error": f"Ticket {ticket_id} not found"}
    return c.to_dict()


@mcp.tool()
def list_comments(ticket_id: str) -> list[dict]:
    """List all comments on a ticket."""
    db = _get_db()
    return [c.to_dict() for c in db.list_comments(ticket_id)]


# ── Sprints ──


@mcp.tool()
def create_sprint(name: str, status: str = "planning") -> dict:
    """Create a new sprint."""
    db = _get_db()
    s = db.create_sprint(name, status)
    return s.to_dict()


@mcp.tool()
def list_sprints() -> list[dict]:
    """List all sprints."""
    db = _get_db()
    return [s.to_dict() for s in db.list_sprints()]


@mcp.tool()
def update_sprint(sprint_id: str, name: Optional[str] = None, status: Optional[str] = None) -> dict:
    """Update a sprint's name or status."""
    db = _get_db()
    fields = {}
    if name is not None:
        fields["name"] = name
    if status is not None:
        fields["status"] = status
    s = db.update_sprint(sprint_id, **fields)
    if not s:
        return {"error": f"Sprint {sprint_id} not found"}
    return s.to_dict()


@mcp.tool()
def add_to_sprint(sprint_id: str, ticket_ids: list[str]) -> list[dict]:
    """Add one or more tickets to a sprint."""
    db = _get_db()
    tickets = db.add_to_sprint(sprint_id, ticket_ids)
    return [t.to_dict() for t in tickets]


@mcp.tool()
def remove_from_sprint(ticket_id: str) -> dict:
    """Remove a ticket from its sprint."""
    db = _get_db()
    t = db.remove_from_sprint(ticket_id)
    if not t:
        return {"error": f"Ticket {ticket_id} not found"}
    return t.to_dict()


# ── Links ──


@mcp.tool()
def link_tickets(from_id: str, to_id: str, relation: str = "blocks") -> dict:
    """Create a dependency link between two tickets. Relations: blocks, blocked_by, relates_to, parent_of, child_of."""
    db = _get_db()
    lnk = db.link_tickets(from_id, to_id, relation)
    if not lnk:
        return {"error": "One or both tickets not found, or invalid relation"}
    return lnk.to_dict()


@mcp.tool()
def unlink_tickets(from_id: str, to_id: str, relation: str = "blocks") -> dict:
    """Remove a link between two tickets."""
    db = _get_db()
    ok = db.unlink_tickets(from_id, to_id, relation)
    if not ok:
        return {"error": "Link not found"}
    return {"unlinked": True, "from_id": from_id, "to_id": to_id, "relation": relation}


# ── Bulk ──


@mcp.tool()
def bulk_update(ticket_ids: list[str], status: Optional[str] = None, priority: Optional[str] = None, sprint_id: Optional[str] = None, assignee: Optional[str] = None) -> list[dict]:
    """Update multiple tickets at once. Only provided fields are changed."""
    db = _get_db()
    fields = {}
    if status is not None:
        fields["status"] = status
    if priority is not None:
        fields["priority"] = priority
    if sprint_id is not None:
        fields["sprint_id"] = sprint_id
    if assignee is not None:
        fields["assignee"] = assignee
    tickets = db.bulk_update(ticket_ids, **fields)
    return [t.to_dict() for t in tickets]


def run_server():
    """Start the MCP server on stdio."""
    mcp.run(transport="stdio")

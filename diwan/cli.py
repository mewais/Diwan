"""Diwan CLI — command-line interface for quick operations."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import click

from .db import DiwanDB


def _get_db() -> DiwanDB:
    db_path = os.environ.get("DIWAN_DB")
    db = DiwanDB(db_path) if db_path else DiwanDB()
    db.init()
    return db


# ── Status display helpers ──

_STATUS_ICONS = {
    "backlog": "\u2592",      # ▒
    "todo": "\U0001f4cb",      # 📋
    "in_progress": "\U0001f504",  # 🔄
    "in_review": "\U0001f50d",    # 🔍
    "done": "\u2705",          # ✅
    "cancelled": "\u274c",     # ❌
}

_PRIORITY_COLORS = {
    "urgent": "red",
    "high": "yellow",
    "medium": "white",
    "low": "blue",
    "none": "bright_black",
}


@click.group()
@click.version_option(package_name="diwan")
def cli():
    """Diwan (ديوان) — Lightweight agent-first issue tracker."""
    pass


@cli.command()
def init():
    """Initialize a Diwan project in the current directory."""
    db = _get_db()
    click.echo(f"Initialized Diwan at {db.db_path}")


@cli.command("create")
@click.argument("title")
@click.option("--description", "-d", default="", help="Ticket description (Markdown)")
@click.option("--status", "-s", default="backlog", type=click.Choice(["backlog", "todo", "in_progress", "in_review", "done", "cancelled"]))
@click.option("--priority", "-p", default="medium", type=click.Choice(["urgent", "high", "medium", "low", "none"]))
@click.option("--labels", "-l", default="", help="Comma-separated labels")
@click.option("--assignee", "-a", default="", help="Assignee name")
@click.option("--sprint", default=None, help="Sprint ID")
@click.option("--parent", default=None, help="Parent ticket ID")
def create_ticket(title, description, status, priority, labels, assignee, sprint, parent):
    """Create a new ticket."""
    db = _get_db()
    label_list = [l.strip() for l in labels.split(",") if l.strip()] if labels else []
    t = db.create_ticket(
        title=title,
        description=description,
        status=status,
        priority=priority,
        labels=label_list,
        assignee=assignee,
        sprint_id=sprint,
        parent_id=parent,
    )
    click.echo(f"Created {t.id}: {t.title}")


@cli.command("list")
@click.option("--status", "-s", default=None, help="Filter by status")
@click.option("--priority", "-p", default=None, help="Filter by priority")
@click.option("--sprint", default=None, help="Filter by sprint ID")
@click.option("--assignee", "-a", default=None, help="Filter by assignee")
@click.option("--labels", "-l", default=None, help="Filter by labels (comma-separated)")
@click.option("--json-output", "--json", "as_json", is_flag=True, help="Output as JSON")
def list_tickets(status, priority, sprint, assignee, labels, as_json):
    """List tickets with optional filters."""
    db = _get_db()
    label_list = [l.strip() for l in labels.split(",") if l.strip()] if labels else None
    tickets = db.list_tickets(
        status=status,
        priority=priority,
        sprint_id=sprint,
        assignee=assignee,
        labels=label_list,
    )

    if as_json:
        click.echo(json.dumps([t.to_dict() for t in tickets], indent=2))
        return

    if not tickets:
        click.echo("No tickets found.")
        return

    # Table output
    click.echo(f"{'ID':<8} {'Title':<40} {'Status':<14} {'Pri':<7} {'Assignee':<15}")
    click.echo("─" * 84)
    for t in tickets:
        icon = _STATUS_ICONS.get(t.status.value, "?")
        click.echo(f"{t.id:<8} {t.title[:39]:<40} {icon} {t.status.value:<12} {t.priority.value:<7} {t.assignee[:14]:<15}")

    # Summary
    by_status: dict[str, int] = {}
    for t in tickets:
        by_status[t.status.value] = by_status.get(t.status.value, 0) + 1
    parts = [f"Total: {len(tickets)}"]
    for s in ["done", "in_progress", "in_review", "todo", "backlog", "cancelled"]:
        if s in by_status:
            parts.append(f"{s}: {by_status[s]}")
    click.echo(f"\n{' | '.join(parts)}")


@cli.command("show")
@click.argument("ticket_id")
def show_ticket(ticket_id):
    """Show full details of a ticket."""
    db = _get_db()
    t = db.get_ticket(ticket_id)
    if not t:
        click.echo(f"Ticket {ticket_id} not found.", err=True)
        sys.exit(1)

    icon = _STATUS_ICONS.get(t.status.value, "?")
    click.echo(f"\n{t.id}: {t.title}")
    click.echo(f"Status: {icon} {t.status.value}  Priority: {t.priority.value}  Assignee: {t.assignee or '(none)'}")
    if t.sprint_id:
        click.echo(f"Sprint: {t.sprint_id}")
    if t.labels:
        click.echo(f"Labels: {', '.join(t.labels)}")
    if t.parent_id:
        click.echo(f"Parent: {t.parent_id}")

    links = db.get_links(t.id)
    if links:
        click.echo("\nLinks:")
        for lnk in links:
            click.echo(f"  {lnk.relation.value} {lnk.to_id}")

    if t.description:
        click.echo(f"\n{t.description}")

    comments = db.list_comments(t.id)
    if comments:
        click.echo("\nComments:")
        for c in comments:
            ts = c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else ""
            author = c.author or "anonymous"
            click.echo(f"  {author} ({ts}):")
            for line in c.content.splitlines():
                click.echo(f"    {line}")


@cli.command("update")
@click.argument("ticket_id")
@click.option("--title", default=None)
@click.option("--description", "-d", default=None)
@click.option("--status", "-s", default=None, type=click.Choice(["backlog", "todo", "in_progress", "in_review", "done", "cancelled"]))
@click.option("--priority", "-p", default=None, type=click.Choice(["urgent", "high", "medium", "low", "none"]))
@click.option("--labels", "-l", default=None, help="Comma-separated labels (replaces existing)")
@click.option("--assignee", "-a", default=None)
@click.option("--sprint", default=None)
def update_ticket(ticket_id, title, description, status, priority, labels, assignee, sprint):
    """Update a ticket's fields."""
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
        fields["labels"] = [l.strip() for l in labels.split(",") if l.strip()]
    if assignee is not None:
        fields["assignee"] = assignee
    if sprint is not None:
        fields["sprint_id"] = sprint

    if not fields:
        click.echo("No fields to update.", err=True)
        sys.exit(1)

    t = db.update_ticket(ticket_id, **fields)
    if not t:
        click.echo(f"Ticket {ticket_id} not found.", err=True)
        sys.exit(1)
    click.echo(f"Updated {t.id}: {t.title}")


@cli.command("delete")
@click.argument("ticket_id")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def delete_ticket(ticket_id, yes):
    """Delete a ticket."""
    db = _get_db()
    if not yes:
        click.confirm(f"Delete {ticket_id}?", abort=True)
    ok = db.delete_ticket(ticket_id)
    if not ok:
        click.echo(f"Ticket {ticket_id} not found.", err=True)
        sys.exit(1)
    click.echo(f"Deleted {ticket_id}")


@cli.command("comment")
@click.argument("ticket_id")
@click.argument("content")
@click.option("--author", "-a", default="", help="Comment author")
def add_comment(ticket_id, content, author):
    """Add a comment to a ticket."""
    db = _get_db()
    c = db.add_comment(ticket_id, content, author)
    if not c:
        click.echo(f"Ticket {ticket_id} not found.", err=True)
        sys.exit(1)
    click.echo(f"Comment added to {ticket_id}")


@cli.command("search")
@click.argument("query")
@click.option("--json-output", "--json", "as_json", is_flag=True, help="Output as JSON")
def search_tickets(query, as_json):
    """Search tickets by text in title or description."""
    db = _get_db()
    tickets = db.search_tickets(query)
    if as_json:
        click.echo(json.dumps([t.to_dict() for t in tickets], indent=2))
        return
    if not tickets:
        click.echo("No tickets found.")
        return
    for t in tickets:
        icon = _STATUS_ICONS.get(t.status.value, "?")
        click.echo(f"{t.id:<8} {icon} {t.status.value:<12} {t.title}")


@cli.command("link")
@click.argument("from_id")
@click.argument("relation", type=click.Choice(["blocks", "blocked_by", "relates_to", "parent_of", "child_of"]))
@click.argument("to_id")
def link_tickets(from_id, relation, to_id):
    """Create a link between two tickets. Usage: diwan link T-001 blocks T-002"""
    db = _get_db()
    lnk = db.link_tickets(from_id, to_id, relation)
    if not lnk:
        click.echo("Failed to create link (ticket not found?).", err=True)
        sys.exit(1)
    click.echo(f"Linked: {from_id} {relation} {to_id}")


@cli.command("unlink")
@click.argument("from_id")
@click.argument("relation", type=click.Choice(["blocks", "blocked_by", "relates_to", "parent_of", "child_of"]))
@click.argument("to_id")
def unlink_tickets(from_id, relation, to_id):
    """Remove a link between two tickets."""
    db = _get_db()
    ok = db.unlink_tickets(from_id, to_id, relation)
    if not ok:
        click.echo("Link not found.", err=True)
        sys.exit(1)
    click.echo(f"Unlinked: {from_id} {relation} {to_id}")


# ── Sprint commands ──


@cli.group("sprint")
def sprint_group():
    """Sprint management commands."""
    pass


@sprint_group.command("create")
@click.argument("name")
@click.option("--status", "-s", default="planning", type=click.Choice(["planning", "active", "completed"]))
def sprint_create(name, status):
    """Create a new sprint."""
    db = _get_db()
    s = db.create_sprint(name, status)
    click.echo(f"Created {s.id}: {s.name}")


@sprint_group.command("list")
def sprint_list():
    """List all sprints."""
    db = _get_db()
    sprints = db.list_sprints()
    if not sprints:
        click.echo("No sprints.")
        return
    for s in sprints:
        click.echo(f"{s.id:<12} {s.name:<30} {s.status.value}")


@sprint_group.command("add")
@click.argument("sprint_id")
@click.argument("ticket_ids", nargs=-1, required=True)
def sprint_add(sprint_id, ticket_ids):
    """Add tickets to a sprint. Usage: diwan sprint add sprint-1 T-001 T-002"""
    db = _get_db()
    tickets = db.add_to_sprint(sprint_id, list(ticket_ids))
    if not tickets:
        click.echo("Sprint not found or no valid tickets.", err=True)
        sys.exit(1)
    for t in tickets:
        click.echo(f"  {t.id} -> {sprint_id}")


@sprint_group.command("complete")
@click.argument("sprint_id")
def sprint_complete(sprint_id):
    """Mark a sprint as completed."""
    db = _get_db()
    s = db.update_sprint(sprint_id, status="completed")
    if not s:
        click.echo(f"Sprint {sprint_id} not found.", err=True)
        sys.exit(1)
    click.echo(f"Completed {s.id}: {s.name}")


# ── MCP server ──


@cli.command("mcp")
def run_mcp():
    """Start the MCP server (stdio transport)."""
    from .mcp_server import run_server
    run_server()


# ── TUI ──


@cli.command("tui")
def run_tui():
    """Open the terminal UI."""
    from .tui.app import DiwanApp
    app = DiwanApp()
    app.run()

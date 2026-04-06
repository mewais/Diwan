"""Ticket detail screen — full view with Markdown rendering."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Markdown, Static

from ..db import DiwanDB
from ..models import Ticket

_STATUS_ICONS = {
    "backlog": "\u2592",
    "todo": "\U0001f4cb",
    "in_progress": "\U0001f504",
    "in_review": "\U0001f50d",
    "done": "\u2705",
    "cancelled": "\u274c",
}


class TicketDetailScreen(Screen):
    """Full ticket detail with Markdown description and comments."""

    BINDINGS = [
        Binding("escape", "go_back", "Back", show=True),
        Binding("b", "go_back", "Back", show=True),
        Binding("s", "cycle_status", "Status", show=True),
    ]

    CSS = """
    #meta {
        height: auto;
        padding: 1 2;
        border-bottom: solid $accent;
    }
    #description-box {
        height: 1fr;
        padding: 0 2;
    }
    #comments-box {
        height: auto;
        max-height: 40%;
        padding: 0 2;
        border-top: solid $accent;
    }
    """

    def __init__(self, db: DiwanDB, ticket_id: str):
        super().__init__()
        self.db = db
        self.ticket_id = ticket_id

    def compose(self) -> ComposeResult:
        t = self.db.get_ticket(self.ticket_id)
        if not t:
            yield Static(f"Ticket {self.ticket_id} not found.")
            return

        icon = _STATUS_ICONS.get(t.status.value, "?")
        links = self.db.get_links(t.id)

        yield Header()

        # Meta section
        meta_lines = [
            f"## {t.id}: {t.title}",
            "",
            f"**Status:** {icon} {t.status.value}  |  **Priority:** {t.priority.value}  |  **Assignee:** {t.assignee or '(none)'}",
        ]
        if t.sprint_id:
            meta_lines.append(f"**Sprint:** {t.sprint_id}")
        if t.labels:
            meta_lines.append(f"**Labels:** {', '.join(t.labels)}")
        if t.parent_id:
            meta_lines.append(f"**Parent:** {t.parent_id}")
        if links:
            link_parts = [f"{lnk.relation.value} {lnk.to_id}" for lnk in links]
            meta_lines.append(f"**Links:** {' | '.join(link_parts)}")
        if t.created_at:
            meta_lines.append(f"**Created:** {t.created_at.strftime('%Y-%m-%d %H:%M')}  |  **Updated:** {t.updated_at.strftime('%Y-%m-%d %H:%M') if t.updated_at else 'n/a'}")

        yield Markdown("\n".join(meta_lines), id="meta")

        # Description
        with VerticalScroll(id="description-box"):
            desc = t.description or "*No description.*"
            yield Markdown(f"### Description\n\n{desc}")

        # Comments
        comments = self.db.list_comments(t.id)
        if comments:
            comment_lines = ["### Comments", ""]
            for c in comments:
                ts = c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else ""
                author = c.author or "anonymous"
                comment_lines.append(f"**{author}** ({ts}):")
                comment_lines.append(f"> {c.content}")
                comment_lines.append("")
            with VerticalScroll(id="comments-box"):
                yield Markdown("\n".join(comment_lines))

        yield Footer()

    def action_go_back(self) -> None:
        self.dismiss(None)

    def action_cycle_status(self) -> None:
        t = self.db.get_ticket(self.ticket_id)
        if not t:
            return
        order = ["backlog", "todo", "in_progress", "in_review", "done"]
        idx = order.index(t.status.value) if t.status.value in order else 0
        next_status = order[(idx + 1) % len(order)]
        self.db.update_ticket(self.ticket_id, status=next_status)
        self.notify(f"{self.ticket_id} -> {next_status}")
        # Refresh by remounting
        self.app.pop_screen()
        self.app.push_screen(TicketDetailScreen(self.db, self.ticket_id))

"""Ticket list screen — main view."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Input, Label, Select, Static

from ..db import DiwanDB
from ..models import Status, Priority
from .ticket_detail import TicketDetailScreen
from .sprint_view import SprintViewScreen


_STATUS_ICONS = {
    "backlog": "\u2592",
    "todo": "\U0001f4cb",
    "in_progress": "\U0001f504",
    "in_review": "\U0001f50d",
    "done": "\u2705",
    "cancelled": "\u274c",
}

_STATUS_OPTIONS = [("All", "all")] + [(s.value, s.value) for s in Status]
_PRIORITY_OPTIONS = [("All", "all")] + [(p.value, p.value) for p in Priority]


class TicketListScreen(Screen):
    """Main ticket list with filters."""

    BINDINGS = [
        Binding("n", "new_ticket", "New", show=True),
        Binding("e", "edit_ticket", "Edit", show=True),
        Binding("c", "comment", "Comment", show=True),
        Binding("s", "sprint_view", "Sprints", show=True),
        Binding("slash", "search", "Search", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("escape", "app.pop_screen", "Back", show=True),
    ]

    CSS = """
    #filters {
        height: 3;
        padding: 0 1;
        dock: top;
    }
    #filters Select {
        width: 20;
        margin: 0 1;
    }
    #filters Input {
        width: 30;
    }
    #summary {
        height: 1;
        dock: bottom;
        padding: 0 1;
        background: $accent;
        color: $text;
    }
    DataTable {
        height: 1fr;
    }
    """

    def __init__(self, db: DiwanDB):
        super().__init__()
        self.db = db
        self._status_filter = "all"
        self._priority_filter = "all"
        self._search_query = ""

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="filters"):
            yield Select(_STATUS_OPTIONS, value="all", id="status_filter", prompt="Status")
            yield Select(_PRIORITY_OPTIONS, value="all", id="priority_filter", prompt="Priority")
            yield Input(placeholder="Search...", id="search_input")
        yield DataTable(id="ticket_table")
        yield Static("", id="summary")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#ticket_table", DataTable)
        table.cursor_type = "row"
        table.add_columns("ID", "Title", "Status", "Pri", "Assignee", "Sprint")
        self._refresh_table()

    def _refresh_table(self) -> None:
        table = self.query_one("#ticket_table", DataTable)
        table.clear()

        status = self._status_filter if self._status_filter != "all" else None
        priority = self._priority_filter if self._priority_filter != "all" else None

        if self._search_query:
            tickets = self.db.search_tickets(self._search_query)
            if status:
                tickets = [t for t in tickets if t.status.value == status]
            if priority:
                tickets = [t for t in tickets if t.priority.value == priority]
        else:
            tickets = self.db.list_tickets(status=status, priority=priority)

        for t in tickets:
            icon = _STATUS_ICONS.get(t.status.value, "?")
            table.add_row(
                t.id,
                t.title[:50],
                f"{icon} {t.status.value}",
                t.priority.value,
                t.assignee or "",
                t.sprint_id or "",
                key=t.id,
            )

        # Summary
        by_status: dict[str, int] = {}
        for t in tickets:
            by_status[t.status.value] = by_status.get(t.status.value, 0) + 1
        parts = [f"Total: {len(tickets)}"]
        for s in ["done", "in_progress", "in_review", "todo", "backlog", "cancelled"]:
            if s in by_status:
                parts.append(f"{s}: {by_status[s]}")
        self.query_one("#summary", Static).update(" | ".join(parts))

    @on(Select.Changed, "#status_filter")
    def _on_status_change(self, event: Select.Changed) -> None:
        self._status_filter = str(event.value) if event.value is not Select.BLANK else "all"
        self._refresh_table()

    @on(Select.Changed, "#priority_filter")
    def _on_priority_change(self, event: Select.Changed) -> None:
        self._priority_filter = str(event.value) if event.value is not Select.BLANK else "all"
        self._refresh_table()

    @on(Input.Submitted, "#search_input")
    def _on_search(self, event: Input.Submitted) -> None:
        self._search_query = event.value.strip()
        self._refresh_table()

    @on(DataTable.RowSelected, "#ticket_table")
    def _on_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key and event.row_key.value:
            self.app.push_screen(
                TicketDetailScreen(self.db, event.row_key.value),
                callback=lambda _: self._refresh_table(),
            )

    def action_new_ticket(self) -> None:
        self.app.push_screen(
            NewTicketScreen(self.db),
            callback=lambda _: self._refresh_table(),
        )

    def action_edit_ticket(self) -> None:
        table = self.query_one("#ticket_table", DataTable)
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        if row_key and row_key.value:
            self.app.push_screen(
                EditTicketScreen(self.db, row_key.value),
                callback=lambda _: self._refresh_table(),
            )

    def action_comment(self) -> None:
        table = self.query_one("#ticket_table", DataTable)
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        if row_key and row_key.value:
            self.app.push_screen(
                AddCommentScreen(self.db, row_key.value),
                callback=lambda _: self._refresh_table(),
            )

    def action_sprint_view(self) -> None:
        self.app.push_screen(
            SprintViewScreen(self.db),
            callback=lambda _: self._refresh_table(),
        )

    def action_search(self) -> None:
        self.query_one("#search_input", Input).focus()

    def action_refresh(self) -> None:
        self._refresh_table()


class NewTicketScreen(Screen):
    """Screen for creating a new ticket."""

    CSS = """
    #form {
        width: 60;
        height: auto;
        margin: 2 4;
        padding: 1 2;
        border: solid $accent;
    }
    #form Label {
        margin-top: 1;
    }
    #form Input {
        margin-bottom: 0;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(self, db: DiwanDB):
        super().__init__()
        self.db = db

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="form"):
            yield Label("New Ticket")
            yield Label("Title:")
            yield Input(id="title", placeholder="Ticket title")
            yield Label("Description:")
            yield Input(id="description", placeholder="Description (Markdown)")
            yield Label("Priority:")
            yield Select(
                [(p.value, p.value) for p in Priority],
                value="medium",
                id="priority",
            )
            yield Label("Assignee:")
            yield Input(id="assignee", placeholder="Assignee name")
            yield Label("Labels (comma-separated):")
            yield Input(id="labels", placeholder="bug, backend")
            yield Label("Press Enter on title to create, Escape to cancel")
        yield Footer()

    @on(Input.Submitted, "#title")
    def _on_submit(self, event: Input.Submitted) -> None:
        title = event.value.strip()
        if not title:
            return
        desc = self.query_one("#description", Input).value
        priority = self.query_one("#priority", Select).value
        assignee = self.query_one("#assignee", Input).value.strip()
        labels_str = self.query_one("#labels", Input).value
        labels = [l.strip() for l in labels_str.split(",") if l.strip()] if labels_str else []

        t = self.db.create_ticket(
            title=title,
            description=desc,
            priority=str(priority) if priority is not Select.BLANK else "medium",
            labels=labels,
            assignee=assignee,
        )
        self.notify(f"Created {t.id}: {t.title}")
        self.dismiss(t.id)

    def action_cancel(self) -> None:
        self.dismiss(None)


class EditTicketScreen(Screen):
    """Screen for editing a ticket's status and fields."""

    CSS = """
    #form {
        width: 60;
        height: auto;
        margin: 2 4;
        padding: 1 2;
        border: solid $accent;
    }
    #form Label {
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(self, db: DiwanDB, ticket_id: str):
        super().__init__()
        self.db = db
        self.ticket_id = ticket_id

    def compose(self) -> ComposeResult:
        t = self.db.get_ticket(self.ticket_id)
        yield Header()
        with Vertical(id="form"):
            yield Label(f"Edit {self.ticket_id}")
            yield Label("Title:")
            yield Input(value=t.title if t else "", id="title")
            yield Label("Status:")
            yield Select(
                [(s.value, s.value) for s in Status],
                value=t.status.value if t else "backlog",
                id="status",
            )
            yield Label("Priority:")
            yield Select(
                [(p.value, p.value) for p in Priority],
                value=t.priority.value if t else "medium",
                id="priority",
            )
            yield Label("Assignee:")
            yield Input(value=t.assignee if t else "", id="assignee")
            yield Label("Labels (comma-separated):")
            yield Input(value=", ".join(t.labels) if t else "", id="labels")
            yield Label("Press Enter on title to save, Escape to cancel")
        yield Footer()

    @on(Input.Submitted, "#title")
    def _on_submit(self, event: Input.Submitted) -> None:
        title = event.value.strip()
        if not title:
            return
        status = self.query_one("#status", Select).value
        priority = self.query_one("#priority", Select).value
        assignee = self.query_one("#assignee", Input).value.strip()
        labels_str = self.query_one("#labels", Input).value
        labels = [l.strip() for l in labels_str.split(",") if l.strip()] if labels_str else []

        self.db.update_ticket(
            self.ticket_id,
            title=title,
            status=str(status) if status is not Select.BLANK else None,
            priority=str(priority) if priority is not Select.BLANK else None,
            assignee=assignee,
            labels=labels,
        )
        self.notify(f"Updated {self.ticket_id}")
        self.dismiss(self.ticket_id)

    def action_cancel(self) -> None:
        self.dismiss(None)


class AddCommentScreen(Screen):
    """Screen for adding a comment."""

    CSS = """
    #form {
        width: 60;
        height: auto;
        margin: 2 4;
        padding: 1 2;
        border: solid $accent;
    }
    #form Label {
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(self, db: DiwanDB, ticket_id: str):
        super().__init__()
        self.db = db
        self.ticket_id = ticket_id

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="form"):
            yield Label(f"Comment on {self.ticket_id}")
            yield Label("Author:")
            yield Input(id="author", placeholder="Your name")
            yield Label("Comment:")
            yield Input(id="content", placeholder="Comment text")
            yield Label("Press Enter on comment to save, Escape to cancel")
        yield Footer()

    @on(Input.Submitted, "#content")
    def _on_submit(self, event: Input.Submitted) -> None:
        content = event.value.strip()
        if not content:
            return
        author = self.query_one("#author", Input).value.strip()
        self.db.add_comment(self.ticket_id, content, author)
        self.notify(f"Comment added to {self.ticket_id}")
        self.dismiss(self.ticket_id)

    def action_cancel(self) -> None:
        self.dismiss(None)

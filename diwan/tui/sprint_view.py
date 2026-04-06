"""Sprint view screen — tickets grouped by status within a sprint."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Label, Markdown, Select, Static

from ..db import DiwanDB

_STATUS_ICONS = {
    "backlog": "\u2592",
    "todo": "\U0001f4cb",
    "in_progress": "\U0001f504",
    "in_review": "\U0001f50d",
    "done": "\u2705",
    "cancelled": "\u274c",
}

_STATUS_ORDER = ["done", "in_review", "in_progress", "todo", "backlog", "cancelled"]


class SprintViewScreen(Screen):
    """View tickets grouped by status within sprints."""

    BINDINGS = [
        Binding("escape", "go_back", "Back", show=True),
        Binding("b", "go_back", "Back", show=True),
        Binding("n", "new_sprint", "New Sprint", show=True),
    ]

    CSS = """
    #sprint-selector {
        height: 3;
        padding: 0 1;
        dock: top;
    }
    #sprint-selector Select {
        width: 40;
    }
    #sprint-content {
        height: 1fr;
        padding: 0 2;
    }
    #progress {
        height: 1;
        dock: bottom;
        padding: 0 1;
        background: $accent;
        color: $text;
    }
    """

    def __init__(self, db: DiwanDB):
        super().__init__()
        self.db = db
        self._current_sprint: str | None = None

    def compose(self) -> ComposeResult:
        sprints = self.db.list_sprints()

        yield Header()

        from textual.containers import Horizontal
        with Horizontal(id="sprint-selector"):
            if sprints:
                options = [(f"{s.id}: {s.name}", s.id) for s in sprints]
                self._current_sprint = sprints[0].id
                yield Select(options, value=sprints[0].id, id="sprint_select")
            else:
                yield Label("No sprints. Press [N] to create one.")

        with VerticalScroll(id="sprint-content"):
            yield Markdown("", id="sprint-md")

        yield Static("", id="progress")
        yield Footer()

    def on_mount(self) -> None:
        if self._current_sprint:
            self._refresh_sprint()

    def _refresh_sprint(self) -> None:
        if not self._current_sprint:
            return

        sprint = self.db.get_sprint(self._current_sprint)
        if not sprint:
            return

        tickets = self.db.list_tickets(sprint_id=self._current_sprint)

        # Group by status
        grouped: dict[str, list] = {s: [] for s in _STATUS_ORDER}
        for t in tickets:
            grouped.setdefault(t.status.value, []).append(t)

        # Build markdown
        lines = [f"## Sprint: {sprint.id} \"{sprint.name}\" — {sprint.status.value}", ""]

        for status in _STATUS_ORDER:
            group = grouped.get(status, [])
            if not group:
                continue
            icon = _STATUS_ICONS.get(status, "?")
            lines.append(f"### {icon} {status.replace('_', ' ').title()} ({len(group)})")
            lines.append("")
            for t in group:
                lines.append(f"- **{t.id}** {t.title} — *{t.assignee or 'unassigned'}*")
            lines.append("")

        md_widget = self.query_one("#sprint-md", Markdown)
        md_widget.update("\n".join(lines))

        # Progress bar
        total = len(tickets)
        done = len(grouped.get("done", []))
        if total > 0:
            pct = done * 100 // total
            bar_len = 30
            filled = pct * bar_len // 100
            bar = "\u2588" * filled + "\u2591" * (bar_len - filled)
            self.query_one("#progress", Static).update(
                f"Progress: {bar} {pct}% ({done}/{total})"
            )
        else:
            self.query_one("#progress", Static).update("No tickets in sprint")

    @on(Select.Changed, "#sprint_select")
    def _on_sprint_change(self, event: Select.Changed) -> None:
        if event.value is not Select.BLANK:
            self._current_sprint = str(event.value)
            self._refresh_sprint()

    def action_go_back(self) -> None:
        self.dismiss(None)

    def action_new_sprint(self) -> None:
        self.app.push_screen(
            NewSprintScreen(self.db),
            callback=lambda _: self._on_sprint_created(),
        )

    def _on_sprint_created(self) -> None:
        # Refresh sprint list — remount screen
        self.app.pop_screen()
        self.app.push_screen(SprintViewScreen(self.db))


class NewSprintScreen(Screen):
    """Screen for creating a new sprint."""

    CSS = """
    #form {
        width: 50;
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

    def __init__(self, db: DiwanDB):
        super().__init__()
        self.db = db

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="form"):
            yield Label("New Sprint")
            yield Label("Name:")
            yield Input(id="name", placeholder="Sprint name")
            yield Label("Press Enter to create, Escape to cancel")
        yield Footer()

    @on(Input.Submitted, "#name")
    def _on_submit(self, event: Input.Submitted) -> None:
        name = event.value.strip()
        if not name:
            return
        s = self.db.create_sprint(name, status="active")
        self.notify(f"Created {s.id}: {s.name}")
        self.dismiss(s.id)

    def action_cancel(self) -> None:
        self.dismiss(None)

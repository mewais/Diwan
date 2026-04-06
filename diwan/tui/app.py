"""Diwan TUI — main Textual application."""

from __future__ import annotations

import os

from textual.app import App, ComposeResult
from textual.binding import Binding

from ..db import DiwanDB
from .ticket_list import TicketListScreen


class DiwanApp(App):
    """Diwan terminal UI."""

    TITLE = "Diwan (ديوان)"
    CSS = """
    Screen {
        background: $surface;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(self):
        super().__init__()
        db_path = os.environ.get("DIWAN_DB")
        self.db = DiwanDB(db_path) if db_path else DiwanDB()
        self.db.init()

    def on_mount(self) -> None:
        self.push_screen(TicketListScreen(self.db))

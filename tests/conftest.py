"""Shared fixtures for Diwan tests."""

import tempfile
from pathlib import Path

import pytest

from diwan.db import DiwanDB


@pytest.fixture
def db(tmp_path):
    """Fresh DiwanDB instance backed by a temp file."""
    db = DiwanDB(tmp_path / "test.db")
    db.init()
    yield db
    db.close()


@pytest.fixture
def populated_db(db):
    """DB with sample data: 4 tickets, 1 sprint, links, comments."""
    db.create_ticket("Fix login bug", priority="high", labels=["backend", "bug"], assignee="alice")
    db.create_ticket("Add user signup", priority="medium", labels=["backend", "auth"], assignee="bob")
    db.create_ticket("Shopping cart API", priority="medium", labels=["backend"], assignee="alice")
    db.create_ticket("Frontend login page", priority="low", labels=["frontend"], assignee="charlie")

    db.create_sprint("Sprint 1", status="active")
    db.add_to_sprint("sprint-1", ["T-001", "T-002", "T-003"])

    db.link_tickets("T-001", "T-003", "blocks")
    db.add_comment("T-001", "Working on this", author="alice")
    db.add_comment("T-001", "Need help with auth flow", author="bob")

    return db

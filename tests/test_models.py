"""Tests for diwan.models."""

import json
from datetime import datetime

import pytest

from diwan.models import (
    Comment,
    Link,
    LinkRelation,
    Priority,
    Sprint,
    SprintStatus,
    Status,
    Ticket,
    _parse_dt,
)


class TestEnums:
    def test_status_values(self):
        assert list(Status) == [
            Status.BACKLOG, Status.TODO, Status.IN_PROGRESS,
            Status.IN_REVIEW, Status.DONE, Status.CANCELLED,
        ]

    def test_priority_values(self):
        assert list(Priority) == [
            Priority.URGENT, Priority.HIGH, Priority.MEDIUM,
            Priority.LOW, Priority.NONE,
        ]

    def test_sprint_status_values(self):
        assert list(SprintStatus) == [
            SprintStatus.PLANNING, SprintStatus.ACTIVE, SprintStatus.COMPLETED,
        ]

    def test_link_relation_values(self):
        assert "blocks" in [r.value for r in LinkRelation]
        assert "blocked_by" in [r.value for r in LinkRelation]

    def test_status_is_str(self):
        assert Status.BACKLOG == "backlog"
        assert isinstance(Status.DONE, str)

    def test_invalid_status_raises(self):
        with pytest.raises(ValueError):
            Status("invalid")

    def test_invalid_priority_raises(self):
        with pytest.raises(ValueError):
            Priority("critical")


class TestTicket:
    def test_from_row(self):
        row = {
            "id": "T-001",
            "title": "Test ticket",
            "description": "A description",
            "status": "todo",
            "priority": "high",
            "labels": '["bug", "backend"]',
            "assignee": "alice",
            "sprint_id": "sprint-1",
            "parent_id": None,
            "created_at": "2026-04-06T10:00:00",
            "updated_at": "2026-04-06T12:00:00",
        }
        t = Ticket.from_row(row)
        assert t.id == "T-001"
        assert t.title == "Test ticket"
        assert t.status == Status.TODO
        assert t.priority == Priority.HIGH
        assert t.labels == ["bug", "backend"]
        assert t.assignee == "alice"
        assert t.sprint_id == "sprint-1"
        assert t.parent_id is None
        assert t.created_at == datetime(2026, 4, 6, 10, 0, 0)

    def test_from_row_empty_labels(self):
        row = {
            "id": "T-001", "title": "Test", "description": "",
            "status": "backlog", "priority": "medium", "labels": "",
            "assignee": "", "sprint_id": None, "parent_id": None,
            "created_at": None, "updated_at": None,
        }
        t = Ticket.from_row(row)
        assert t.labels == []

    def test_to_dict(self):
        t = Ticket(id="T-001", title="Test", status=Status.DONE, priority=Priority.URGENT)
        d = t.to_dict()
        assert d["id"] == "T-001"
        assert d["status"] == "done"
        assert d["priority"] == "urgent"
        assert d["labels"] == []

    def test_to_dict_roundtrip(self):
        row = {
            "id": "T-005", "title": "Roundtrip", "description": "desc",
            "status": "in_progress", "priority": "low",
            "labels": '["a", "b"]', "assignee": "bob",
            "sprint_id": "sprint-2", "parent_id": "T-001",
            "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-02T00:00:00",
        }
        t = Ticket.from_row(row)
        d = t.to_dict()
        assert d["id"] == "T-005"
        assert d["labels"] == ["a", "b"]
        assert d["sprint_id"] == "sprint-2"
        assert d["parent_id"] == "T-001"


class TestComment:
    def test_from_row(self):
        row = {
            "id": 1, "ticket_id": "T-001", "author": "alice",
            "content": "Hello", "created_at": "2026-04-06T10:00:00",
        }
        c = Comment.from_row(row)
        assert c.id == 1
        assert c.author == "alice"
        assert c.content == "Hello"

    def test_to_dict(self):
        c = Comment(id=1, ticket_id="T-001", author="bob", content="world")
        d = c.to_dict()
        assert d["ticket_id"] == "T-001"
        assert d["author"] == "bob"


class TestSprint:
    def test_from_row(self):
        row = {"id": "sprint-1", "name": "Sprint 1", "status": "active", "created_at": None}
        s = Sprint.from_row(row)
        assert s.id == "sprint-1"
        assert s.status == SprintStatus.ACTIVE

    def test_to_dict(self):
        s = Sprint(id="sprint-1", name="S1", status=SprintStatus.COMPLETED)
        d = s.to_dict()
        assert d["status"] == "completed"


class TestLink:
    def test_from_row(self):
        row = {"from_id": "T-001", "to_id": "T-002", "relation": "blocks"}
        lnk = Link.from_row(row)
        assert lnk.relation == LinkRelation.BLOCKS

    def test_to_dict(self):
        lnk = Link(from_id="T-001", to_id="T-002", relation=LinkRelation.RELATES_TO)
        d = lnk.to_dict()
        assert d["relation"] == "relates_to"


class TestParseDt:
    def test_valid(self):
        assert _parse_dt("2026-04-06T10:00:00") == datetime(2026, 4, 6, 10, 0, 0)

    def test_none(self):
        assert _parse_dt(None) is None

    def test_empty(self):
        assert _parse_dt("") is None

    def test_invalid(self):
        assert _parse_dt("not-a-date") is None

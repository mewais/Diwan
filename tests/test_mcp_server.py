"""Tests for diwan.mcp_server — MCP tool functions."""

import os

import pytest

import diwan.mcp_server as mcp_mod


@pytest.fixture(autouse=True)
def reset_db(tmp_path, monkeypatch):
    """Point MCP server at a fresh temp DB for each test."""
    monkeypatch.setenv("DIWAN_DB", str(tmp_path / "mcp_test.db"))
    mcp_mod._db = None  # reset singleton
    yield
    mcp_mod._db = None


class TestCreateTicket:
    def test_create_simple(self):
        result = mcp_mod.create_ticket(title="Test ticket")
        assert result["id"] == "T-001"
        assert result["title"] == "Test ticket"
        assert result["status"] == "backlog"

    def test_create_with_all_fields(self):
        mcp_mod.create_sprint(name="S1", status="active")
        result = mcp_mod.create_ticket(
            title="Full ticket",
            description="desc",
            status="todo",
            priority="high",
            labels=["bug"],
            assignee="alice",
            sprint_id="sprint-1",
        )
        assert result["status"] == "todo"
        assert result["priority"] == "high"
        assert result["labels"] == ["bug"]
        assert result["assignee"] == "alice"

    def test_create_sequential(self):
        mcp_mod.create_ticket(title="A")
        mcp_mod.create_ticket(title="B")
        r3 = mcp_mod.create_ticket(title="C")
        assert r3["id"] == "T-003"


class TestGetTicket:
    def test_get_existing(self):
        mcp_mod.create_ticket(title="Test")
        result = mcp_mod.get_ticket(ticket_id="T-001")
        assert result["title"] == "Test"
        assert "links" in result
        assert "comments" in result

    def test_get_nonexistent(self):
        result = mcp_mod.get_ticket(ticket_id="T-999")
        assert "error" in result

    def test_get_includes_links(self):
        mcp_mod.create_ticket(title="A")
        mcp_mod.create_ticket(title="B")
        mcp_mod.link_tickets(from_id="T-001", to_id="T-002", relation="blocks")
        result = mcp_mod.get_ticket(ticket_id="T-001")
        assert len(result["links"]) == 1
        assert result["links"][0]["relation"] == "blocks"

    def test_get_includes_comments(self):
        mcp_mod.create_ticket(title="A")
        mcp_mod.add_comment(ticket_id="T-001", content="Hello", author="alice")
        result = mcp_mod.get_ticket(ticket_id="T-001")
        assert len(result["comments"]) == 1


class TestUpdateTicket:
    def test_update_status(self):
        mcp_mod.create_ticket(title="Test")
        result = mcp_mod.update_ticket(ticket_id="T-001", status="done")
        assert result["status"] == "done"

    def test_update_nonexistent(self):
        result = mcp_mod.update_ticket(ticket_id="T-999", status="done")
        assert "error" in result

    def test_update_multiple_fields(self):
        mcp_mod.create_ticket(title="Test")
        result = mcp_mod.update_ticket(
            ticket_id="T-001", title="New", priority="urgent", assignee="bob"
        )
        assert result["title"] == "New"
        assert result["priority"] == "urgent"
        assert result["assignee"] == "bob"


class TestListTickets:
    def test_list_empty(self):
        assert mcp_mod.list_tickets() == []

    def test_list_all(self):
        mcp_mod.create_ticket(title="A")
        mcp_mod.create_ticket(title="B")
        result = mcp_mod.list_tickets()
        assert len(result) == 2

    def test_list_filter_status(self):
        mcp_mod.create_ticket(title="A", status="todo")
        mcp_mod.create_ticket(title="B", status="done")
        result = mcp_mod.list_tickets(status="todo")
        assert len(result) == 1
        assert result[0]["title"] == "A"

    def test_list_filter_assignee(self):
        mcp_mod.create_ticket(title="A", assignee="alice")
        mcp_mod.create_ticket(title="B", assignee="bob")
        result = mcp_mod.list_tickets(assignee="alice")
        assert len(result) == 1


class TestSearchTickets:
    def test_search(self):
        mcp_mod.create_ticket(title="Fix login bug")
        mcp_mod.create_ticket(title="Add signup")
        result = mcp_mod.search_tickets(query="login")
        assert len(result) == 1

    def test_search_empty(self):
        result = mcp_mod.search_tickets(query="nonexistent")
        assert result == []


class TestDeleteTicket:
    def test_delete(self):
        mcp_mod.create_ticket(title="Test")
        result = mcp_mod.delete_ticket(ticket_id="T-001")
        assert result["deleted"] == "T-001"

    def test_delete_nonexistent(self):
        result = mcp_mod.delete_ticket(ticket_id="T-999")
        assert "error" in result


class TestComments:
    def test_add_comment(self):
        mcp_mod.create_ticket(title="Test")
        result = mcp_mod.add_comment(ticket_id="T-001", content="Hello", author="alice")
        assert result["content"] == "Hello"
        assert result["author"] == "alice"

    def test_add_comment_nonexistent(self):
        result = mcp_mod.add_comment(ticket_id="T-999", content="Ghost")
        assert "error" in result

    def test_list_comments(self):
        mcp_mod.create_ticket(title="Test")
        mcp_mod.add_comment(ticket_id="T-001", content="First")
        mcp_mod.add_comment(ticket_id="T-001", content="Second")
        result = mcp_mod.list_comments(ticket_id="T-001")
        assert len(result) == 2


class TestSprints:
    def test_create_sprint(self):
        result = mcp_mod.create_sprint(name="Sprint 1")
        assert result["id"] == "sprint-1"
        assert result["name"] == "Sprint 1"

    def test_list_sprints(self):
        mcp_mod.create_sprint(name="S1")
        mcp_mod.create_sprint(name="S2")
        result = mcp_mod.list_sprints()
        assert len(result) == 2

    def test_update_sprint(self):
        mcp_mod.create_sprint(name="S1")
        result = mcp_mod.update_sprint(sprint_id="sprint-1", status="completed")
        assert result["status"] == "completed"

    def test_update_sprint_nonexistent(self):
        result = mcp_mod.update_sprint(sprint_id="sprint-99", status="completed")
        assert "error" in result

    def test_add_to_sprint(self):
        mcp_mod.create_sprint(name="S1")
        mcp_mod.create_ticket(title="A")
        mcp_mod.create_ticket(title="B")
        result = mcp_mod.add_to_sprint(sprint_id="sprint-1", ticket_ids=["T-001", "T-002"])
        assert len(result) == 2
        assert all(t["sprint_id"] == "sprint-1" for t in result)

    def test_remove_from_sprint(self):
        mcp_mod.create_sprint(name="S1")
        mcp_mod.create_ticket(title="A", sprint_id="sprint-1")
        result = mcp_mod.remove_from_sprint(ticket_id="T-001")
        assert result["sprint_id"] is None


class TestLinks:
    def test_link(self):
        mcp_mod.create_ticket(title="A")
        mcp_mod.create_ticket(title="B")
        result = mcp_mod.link_tickets(from_id="T-001", to_id="T-002", relation="blocks")
        assert result["relation"] == "blocks"

    def test_link_nonexistent(self):
        mcp_mod.create_ticket(title="A")
        result = mcp_mod.link_tickets(from_id="T-001", to_id="T-999", relation="blocks")
        assert "error" in result

    def test_unlink(self):
        mcp_mod.create_ticket(title="A")
        mcp_mod.create_ticket(title="B")
        mcp_mod.link_tickets(from_id="T-001", to_id="T-002", relation="blocks")
        result = mcp_mod.unlink_tickets(from_id="T-001", to_id="T-002", relation="blocks")
        assert result["unlinked"] is True

    def test_unlink_nonexistent(self):
        result = mcp_mod.unlink_tickets(from_id="T-001", to_id="T-002", relation="blocks")
        assert "error" in result


class TestBulkUpdate:
    def test_bulk_update(self):
        mcp_mod.create_ticket(title="A")
        mcp_mod.create_ticket(title="B")
        mcp_mod.create_ticket(title="C")
        result = mcp_mod.bulk_update(
            ticket_ids=["T-001", "T-002"], status="done"
        )
        assert len(result) == 2
        assert all(t["status"] == "done" for t in result)
        # T-003 unchanged
        t3 = mcp_mod.get_ticket(ticket_id="T-003")
        assert t3["status"] == "backlog"

    def test_bulk_update_partial(self):
        mcp_mod.create_ticket(title="A")
        result = mcp_mod.bulk_update(
            ticket_ids=["T-001", "T-999"], status="done"
        )
        assert len(result) == 1

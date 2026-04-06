"""Tests for diwan.db — SQLite storage layer."""

import sqlite3
from pathlib import Path

import pytest

from diwan.db import DiwanDB
from diwan.models import LinkRelation, Priority, SprintStatus, Status


# ── Initialization ──


class TestInit:
    def test_creates_db_file(self, tmp_path):
        db_path = tmp_path / "sub" / "test.db"
        db = DiwanDB(db_path)
        db.init()
        assert db_path.exists()
        db.close()

    def test_creates_tables(self, db):
        tables = {
            row[0]
            for row in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert {"tickets", "comments", "sprints", "links"} <= tables

    def test_wal_mode(self, db):
        mode = db.conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"

    def test_foreign_keys_on(self, db):
        fk = db.conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1

    def test_idempotent_init(self, db):
        db.init()
        db.init()  # should not raise


# ── Ticket CRUD ──


class TestTicketCreate:
    def test_first_ticket_id(self, db):
        t = db.create_ticket("First")
        assert t.id == "T-001"

    def test_sequential_ids(self, db):
        t1 = db.create_ticket("First")
        t2 = db.create_ticket("Second")
        t3 = db.create_ticket("Third")
        assert t1.id == "T-001"
        assert t2.id == "T-002"
        assert t3.id == "T-003"

    def test_defaults(self, db):
        t = db.create_ticket("Minimal")
        assert t.status == Status.BACKLOG
        assert t.priority == Priority.MEDIUM
        assert t.labels == []
        assert t.assignee == ""
        assert t.sprint_id is None
        assert t.parent_id is None
        assert t.created_at is not None
        assert t.updated_at is not None

    def test_all_fields(self, db):
        db.create_sprint("S1", status="active")
        t = db.create_ticket(
            title="Full ticket",
            description="A description",
            status="todo",
            priority="high",
            labels=["bug", "urgent"],
            assignee="alice",
            sprint_id="sprint-1",
        )
        assert t.title == "Full ticket"
        assert t.description == "A description"
        assert t.status == Status.TODO
        assert t.priority == Priority.HIGH
        assert t.labels == ["bug", "urgent"]
        assert t.assignee == "alice"
        assert t.sprint_id == "sprint-1"

    def test_invalid_status_raises(self, db):
        with pytest.raises(ValueError):
            db.create_ticket("Bad", status="invalid")

    def test_invalid_priority_raises(self, db):
        with pytest.raises(ValueError):
            db.create_ticket("Bad", priority="critical")

    def test_parent_id(self, db):
        parent = db.create_ticket("Parent")
        child = db.create_ticket("Child", parent_id=parent.id)
        assert child.parent_id == "T-001"


class TestTicketGet:
    def test_get_existing(self, db):
        db.create_ticket("Test")
        t = db.get_ticket("T-001")
        assert t is not None
        assert t.title == "Test"

    def test_get_nonexistent(self, db):
        assert db.get_ticket("T-999") is None


class TestTicketUpdate:
    def test_update_status(self, db):
        db.create_ticket("Test")
        t = db.update_ticket("T-001", status="in_progress")
        assert t.status == Status.IN_PROGRESS

    def test_update_priority(self, db):
        db.create_ticket("Test")
        t = db.update_ticket("T-001", priority="urgent")
        assert t.priority == Priority.URGENT

    def test_update_title(self, db):
        db.create_ticket("Old title")
        t = db.update_ticket("T-001", title="New title")
        assert t.title == "New title"

    def test_update_labels(self, db):
        db.create_ticket("Test", labels=["a"])
        t = db.update_ticket("T-001", labels=["b", "c"])
        assert t.labels == ["b", "c"]

    def test_update_assignee(self, db):
        db.create_ticket("Test")
        t = db.update_ticket("T-001", assignee="bob")
        assert t.assignee == "bob"

    def test_update_multiple_fields(self, db):
        db.create_ticket("Test")
        t = db.update_ticket("T-001", status="done", priority="low", assignee="charlie")
        assert t.status == Status.DONE
        assert t.priority == Priority.LOW
        assert t.assignee == "charlie"

    def test_update_nonexistent(self, db):
        assert db.update_ticket("T-999", status="done") is None

    def test_update_invalid_status(self, db):
        db.create_ticket("Test")
        with pytest.raises(ValueError):
            db.update_ticket("T-001", status="invalid")

    def test_update_no_fields(self, db):
        db.create_ticket("Test")
        t = db.update_ticket("T-001")  # no fields
        assert t.title == "Test"  # unchanged

    def test_update_ignores_unknown_fields(self, db):
        db.create_ticket("Test")
        t = db.update_ticket("T-001", unknown_field="value")
        assert t.title == "Test"

    def test_updated_at_changes(self, db):
        t1 = db.create_ticket("Test")
        t2 = db.update_ticket("T-001", title="Changed")
        assert t2.updated_at >= t1.updated_at


class TestTicketDelete:
    def test_delete_existing(self, db):
        db.create_ticket("Test")
        assert db.delete_ticket("T-001") is True
        assert db.get_ticket("T-001") is None

    def test_delete_nonexistent(self, db):
        assert db.delete_ticket("T-999") is False

    def test_delete_cascades_comments(self, db):
        db.create_ticket("Test")
        db.add_comment("T-001", "A comment")
        db.delete_ticket("T-001")
        assert db.list_comments("T-001") == []

    def test_delete_cascades_links(self, db):
        db.create_ticket("A")
        db.create_ticket("B")
        db.link_tickets("T-001", "T-002", "blocks")
        db.delete_ticket("T-001")
        assert db.get_links("T-002") == []


# ── Ticket Listing & Search ──


class TestTicketList:
    def test_empty(self, db):
        assert db.list_tickets() == []

    def test_list_all(self, populated_db):
        tickets = populated_db.list_tickets()
        assert len(tickets) == 4

    def test_filter_by_status(self, populated_db):
        populated_db.update_ticket("T-001", status="in_progress")
        tickets = populated_db.list_tickets(status="in_progress")
        assert len(tickets) == 1
        assert tickets[0].id == "T-001"

    def test_filter_by_priority(self, populated_db):
        tickets = populated_db.list_tickets(priority="high")
        assert len(tickets) == 1
        assert tickets[0].id == "T-001"

    def test_filter_by_sprint(self, populated_db):
        tickets = populated_db.list_tickets(sprint_id="sprint-1")
        assert len(tickets) == 3

    def test_filter_by_assignee(self, populated_db):
        tickets = populated_db.list_tickets(assignee="alice")
        assert len(tickets) == 2

    def test_filter_by_labels(self, populated_db):
        tickets = populated_db.list_tickets(labels=["bug"])
        assert len(tickets) == 1
        assert tickets[0].id == "T-001"

    def test_filter_by_labels_multiple(self, populated_db):
        tickets = populated_db.list_tickets(labels=["bug", "frontend"])
        assert len(tickets) == 2  # T-001 (bug) and T-004 (frontend)

    def test_combined_filters(self, populated_db):
        tickets = populated_db.list_tickets(assignee="alice", sprint_id="sprint-1")
        assert len(tickets) == 2  # T-001 and T-003

    def test_order_by_id(self, populated_db):
        tickets = populated_db.list_tickets()
        ids = [t.id for t in tickets]
        assert ids == ["T-001", "T-002", "T-003", "T-004"]

    def test_filter_by_parent(self, db):
        db.create_ticket("Parent")
        db.create_ticket("Child 1", parent_id="T-001")
        db.create_ticket("Child 2", parent_id="T-001")
        db.create_ticket("Standalone")
        children = db.list_tickets(parent_id="T-001")
        assert len(children) == 2


class TestTicketSearch:
    def test_search_title(self, populated_db):
        results = populated_db.search_tickets("login")
        assert len(results) == 2  # T-001 "Fix login bug", T-004 "Frontend login page"

    def test_search_description(self, db):
        db.create_ticket("Test", description="This is about authentication")
        results = db.search_tickets("authentication")
        assert len(results) == 1

    def test_search_case_insensitive(self, populated_db):
        results = populated_db.search_tickets("LOGIN")
        assert len(results) == 2

    def test_search_no_results(self, populated_db):
        results = populated_db.search_tickets("nonexistent")
        assert len(results) == 0


class TestBulkUpdate:
    def test_bulk_status(self, populated_db):
        results = populated_db.bulk_update(["T-001", "T-002"], status="done")
        assert len(results) == 2
        assert all(t.status == Status.DONE for t in results)

    def test_bulk_with_invalid_id(self, populated_db):
        results = populated_db.bulk_update(["T-001", "T-999"], status="done")
        assert len(results) == 1  # only T-001

    def test_bulk_empty_list(self, populated_db):
        results = populated_db.bulk_update([], status="done")
        assert results == []


# ── Comments ──


class TestComments:
    def test_add_comment(self, db):
        db.create_ticket("Test")
        c = db.add_comment("T-001", "Hello", author="alice")
        assert c is not None
        assert c.content == "Hello"
        assert c.author == "alice"
        assert c.ticket_id == "T-001"
        assert c.id >= 1

    def test_add_comment_no_author(self, db):
        db.create_ticket("Test")
        c = db.add_comment("T-001", "Anon comment")
        assert c.author == ""

    def test_add_comment_nonexistent_ticket(self, db):
        assert db.add_comment("T-999", "Ghost") is None

    def test_list_comments(self, populated_db):
        comments = populated_db.list_comments("T-001")
        assert len(comments) == 2
        assert comments[0].content == "Working on this"
        assert comments[1].content == "Need help with auth flow"

    def test_list_comments_empty(self, populated_db):
        comments = populated_db.list_comments("T-002")
        assert comments == []

    def test_comment_ordering(self, db):
        db.create_ticket("Test")
        db.add_comment("T-001", "First")
        db.add_comment("T-001", "Second")
        db.add_comment("T-001", "Third")
        comments = db.list_comments("T-001")
        assert [c.content for c in comments] == ["First", "Second", "Third"]


# ── Sprints ──


class TestSprints:
    def test_create_sprint(self, db):
        s = db.create_sprint("Sprint 1")
        assert s.id == "sprint-1"
        assert s.name == "Sprint 1"
        assert s.status == SprintStatus.PLANNING

    def test_create_sprint_active(self, db):
        s = db.create_sprint("Sprint 1", status="active")
        assert s.status == SprintStatus.ACTIVE

    def test_sequential_sprint_ids(self, db):
        s1 = db.create_sprint("S1")
        s2 = db.create_sprint("S2")
        s3 = db.create_sprint("S3")
        assert s1.id == "sprint-1"
        assert s2.id == "sprint-2"
        assert s3.id == "sprint-3"

    def test_invalid_sprint_status(self, db):
        with pytest.raises(ValueError):
            db.create_sprint("Bad", status="invalid")

    def test_get_sprint(self, db):
        db.create_sprint("Test")
        s = db.get_sprint("sprint-1")
        assert s is not None
        assert s.name == "Test"

    def test_get_sprint_nonexistent(self, db):
        assert db.get_sprint("sprint-99") is None

    def test_list_sprints(self, db):
        db.create_sprint("S1")
        db.create_sprint("S2")
        sprints = db.list_sprints()
        assert len(sprints) == 2

    def test_update_sprint_status(self, db):
        db.create_sprint("S1")
        s = db.update_sprint("sprint-1", status="completed")
        assert s.status == SprintStatus.COMPLETED

    def test_update_sprint_name(self, db):
        db.create_sprint("Old Name")
        s = db.update_sprint("sprint-1", name="New Name")
        assert s.name == "New Name"

    def test_update_sprint_nonexistent(self, db):
        assert db.update_sprint("sprint-99", status="completed") is None

    def test_add_to_sprint(self, db):
        db.create_sprint("S1")
        db.create_ticket("T1")
        db.create_ticket("T2")
        results = db.add_to_sprint("sprint-1", ["T-001", "T-002"])
        assert len(results) == 2
        assert all(t.sprint_id == "sprint-1" for t in results)

    def test_add_to_nonexistent_sprint(self, db):
        db.create_ticket("T1")
        assert db.add_to_sprint("sprint-99", ["T-001"]) == []

    def test_remove_from_sprint(self, db):
        db.create_sprint("S1")
        db.create_ticket("T1", sprint_id="sprint-1")
        t = db.remove_from_sprint("T-001")
        assert t.sprint_id is None


# ── Links ──


class TestLinks:
    def test_link_blocks(self, db):
        db.create_ticket("A")
        db.create_ticket("B")
        lnk = db.link_tickets("T-001", "T-002", "blocks")
        assert lnk is not None
        assert lnk.relation == LinkRelation.BLOCKS

    def test_bidirectional_links(self, db):
        db.create_ticket("A")
        db.create_ticket("B")
        db.link_tickets("T-001", "T-002", "blocks")

        links_a = db.get_links("T-001")
        links_b = db.get_links("T-002")
        assert len(links_a) == 1
        assert links_a[0].relation == LinkRelation.BLOCKS
        assert links_a[0].to_id == "T-002"
        assert len(links_b) == 1
        assert links_b[0].relation == LinkRelation.BLOCKED_BY
        assert links_b[0].to_id == "T-001"

    def test_link_parent_child(self, db):
        db.create_ticket("Parent")
        db.create_ticket("Child")
        db.link_tickets("T-001", "T-002", "parent_of")

        links_parent = db.get_links("T-001")
        links_child = db.get_links("T-002")
        assert links_parent[0].relation == LinkRelation.PARENT_OF
        assert links_child[0].relation == LinkRelation.CHILD_OF

    def test_link_relates_to(self, db):
        db.create_ticket("A")
        db.create_ticket("B")
        db.link_tickets("T-001", "T-002", "relates_to")

        links_a = db.get_links("T-001")
        links_b = db.get_links("T-002")
        assert links_a[0].relation == LinkRelation.RELATES_TO
        assert links_b[0].relation == LinkRelation.RELATES_TO

    def test_link_nonexistent_ticket(self, db):
        db.create_ticket("A")
        assert db.link_tickets("T-001", "T-999", "blocks") is None

    def test_link_invalid_relation(self, db):
        db.create_ticket("A")
        db.create_ticket("B")
        with pytest.raises(ValueError):
            db.link_tickets("T-001", "T-002", "invalid")

    def test_duplicate_link_ignored(self, db):
        db.create_ticket("A")
        db.create_ticket("B")
        db.link_tickets("T-001", "T-002", "blocks")
        db.link_tickets("T-001", "T-002", "blocks")  # no error
        links = db.get_links("T-001")
        assert len(links) == 1

    def test_unlink(self, db):
        db.create_ticket("A")
        db.create_ticket("B")
        db.link_tickets("T-001", "T-002", "blocks")
        assert db.unlink_tickets("T-001", "T-002", "blocks") is True
        assert db.get_links("T-001") == []
        assert db.get_links("T-002") == []  # inverse also removed

    def test_unlink_nonexistent(self, db):
        assert db.unlink_tickets("T-001", "T-002", "blocks") is False

    def test_multiple_links_between_same_tickets(self, db):
        db.create_ticket("A")
        db.create_ticket("B")
        db.link_tickets("T-001", "T-002", "blocks")
        db.link_tickets("T-001", "T-002", "relates_to")
        links = db.get_links("T-001")
        assert len(links) == 2


# ── ID generation edge cases ──


class TestIdGeneration:
    def test_id_after_delete(self, db):
        db.create_ticket("First")
        db.create_ticket("Second")
        db.delete_ticket("T-001")
        t3 = db.create_ticket("Third")
        assert t3.id == "T-003"  # continues from max, not reuses

    def test_many_tickets(self, db):
        for i in range(15):
            db.create_ticket(f"Ticket {i+1}")
        t = db.get_ticket("T-015")
        assert t is not None
        assert t.title == "Ticket 15"

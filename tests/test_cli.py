"""Tests for diwan.cli — Click CLI commands."""

import json
import os

import pytest
from click.testing import CliRunner

from diwan.cli import cli


@pytest.fixture
def runner(tmp_path):
    """CLI runner with DIWAN_DB pointing to tmp dir."""
    r = CliRunner()
    env = {"DIWAN_DB": str(tmp_path / "test.db")}
    # Init DB
    r.invoke(cli, ["init"], env=env)
    return r, env


class TestInit:
    def test_init(self, tmp_path):
        r = CliRunner()
        result = r.invoke(cli, ["init"], env={"DIWAN_DB": str(tmp_path / "test.db")})
        assert result.exit_code == 0
        assert "Initialized" in result.output


class TestCreate:
    def test_create_simple(self, runner):
        r, env = runner
        result = r.invoke(cli, ["create", "Fix bug"], env=env)
        assert result.exit_code == 0
        assert "Created T-001" in result.output

    def test_create_with_options(self, runner):
        r, env = runner
        result = r.invoke(cli, [
            "create", "Auth feature",
            "--priority", "high",
            "--labels", "backend,auth",
            "--assignee", "alice",
        ], env=env)
        assert result.exit_code == 0
        assert "T-001" in result.output

    def test_create_with_description(self, runner):
        r, env = runner
        result = r.invoke(cli, [
            "create", "Test ticket",
            "-d", "## Description\nWith markdown",
        ], env=env)
        assert result.exit_code == 0


class TestList:
    def test_list_empty(self, runner):
        r, env = runner
        result = r.invoke(cli, ["list"], env=env)
        assert result.exit_code == 0
        assert "No tickets found" in result.output

    def test_list_with_tickets(self, runner):
        r, env = runner
        r.invoke(cli, ["create", "Ticket 1"], env=env)
        r.invoke(cli, ["create", "Ticket 2"], env=env)
        result = r.invoke(cli, ["list"], env=env)
        assert result.exit_code == 0
        assert "T-001" in result.output
        assert "T-002" in result.output
        assert "Total: 2" in result.output

    def test_list_filter_status(self, runner):
        r, env = runner
        r.invoke(cli, ["create", "Ticket 1"], env=env)
        r.invoke(cli, ["update", "T-001", "-s", "done"], env=env)
        r.invoke(cli, ["create", "Ticket 2"], env=env)
        result = r.invoke(cli, ["list", "--status", "done"], env=env)
        assert "T-001" in result.output
        assert "T-002" not in result.output

    def test_list_json(self, runner):
        r, env = runner
        r.invoke(cli, ["create", "Test"], env=env)
        result = r.invoke(cli, ["list", "--json"], env=env)
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["id"] == "T-001"


class TestShow:
    def test_show_ticket(self, runner):
        r, env = runner
        r.invoke(cli, ["create", "Test ticket", "-p", "high", "-l", "bug,backend"], env=env)
        result = r.invoke(cli, ["show", "T-001"], env=env)
        assert result.exit_code == 0
        assert "T-001: Test ticket" in result.output
        assert "high" in result.output
        assert "bug" in result.output

    def test_show_nonexistent(self, runner):
        r, env = runner
        result = r.invoke(cli, ["show", "T-999"], env=env)
        assert result.exit_code != 0

    def test_show_with_comments(self, runner):
        r, env = runner
        r.invoke(cli, ["create", "Test"], env=env)
        r.invoke(cli, ["comment", "T-001", "Hello world", "-a", "alice"], env=env)
        result = r.invoke(cli, ["show", "T-001"], env=env)
        assert "alice" in result.output
        assert "Hello world" in result.output

    def test_show_with_links(self, runner):
        r, env = runner
        r.invoke(cli, ["create", "A"], env=env)
        r.invoke(cli, ["create", "B"], env=env)
        r.invoke(cli, ["link", "T-001", "blocks", "T-002"], env=env)
        result = r.invoke(cli, ["show", "T-001"], env=env)
        assert "blocks" in result.output
        assert "T-002" in result.output


class TestUpdate:
    def test_update_status(self, runner):
        r, env = runner
        r.invoke(cli, ["create", "Test"], env=env)
        result = r.invoke(cli, ["update", "T-001", "-s", "in_progress"], env=env)
        assert result.exit_code == 0
        assert "Updated T-001" in result.output

    def test_update_nonexistent(self, runner):
        r, env = runner
        result = r.invoke(cli, ["update", "T-999", "-s", "done"], env=env)
        assert result.exit_code != 0

    def test_update_no_fields(self, runner):
        r, env = runner
        r.invoke(cli, ["create", "Test"], env=env)
        result = r.invoke(cli, ["update", "T-001"], env=env)
        assert result.exit_code != 0
        assert "No fields" in result.output


class TestDelete:
    def test_delete_with_confirm(self, runner):
        r, env = runner
        r.invoke(cli, ["create", "Test"], env=env)
        result = r.invoke(cli, ["delete", "T-001", "-y"], env=env)
        assert result.exit_code == 0
        assert "Deleted T-001" in result.output

    def test_delete_nonexistent(self, runner):
        r, env = runner
        result = r.invoke(cli, ["delete", "T-999", "-y"], env=env)
        assert result.exit_code != 0


class TestComment:
    def test_add_comment(self, runner):
        r, env = runner
        r.invoke(cli, ["create", "Test"], env=env)
        result = r.invoke(cli, ["comment", "T-001", "A comment", "-a", "bob"], env=env)
        assert result.exit_code == 0
        assert "Comment added" in result.output

    def test_comment_nonexistent(self, runner):
        r, env = runner
        result = r.invoke(cli, ["comment", "T-999", "Ghost"], env=env)
        assert result.exit_code != 0


class TestSearch:
    def test_search_found(self, runner):
        r, env = runner
        r.invoke(cli, ["create", "Fix login bug"], env=env)
        r.invoke(cli, ["create", "Add signup"], env=env)
        result = r.invoke(cli, ["search", "login"], env=env)
        assert result.exit_code == 0
        assert "T-001" in result.output
        assert "T-002" not in result.output

    def test_search_not_found(self, runner):
        r, env = runner
        r.invoke(cli, ["create", "Test"], env=env)
        result = r.invoke(cli, ["search", "nonexistent"], env=env)
        assert "No tickets found" in result.output

    def test_search_json(self, runner):
        r, env = runner
        r.invoke(cli, ["create", "Fix login bug"], env=env)
        result = r.invoke(cli, ["search", "login", "--json"], env=env)
        data = json.loads(result.output)
        assert len(data) == 1


class TestLink:
    def test_link(self, runner):
        r, env = runner
        r.invoke(cli, ["create", "A"], env=env)
        r.invoke(cli, ["create", "B"], env=env)
        result = r.invoke(cli, ["link", "T-001", "blocks", "T-002"], env=env)
        assert result.exit_code == 0
        assert "Linked" in result.output

    def test_link_nonexistent(self, runner):
        r, env = runner
        r.invoke(cli, ["create", "A"], env=env)
        result = r.invoke(cli, ["link", "T-001", "blocks", "T-999"], env=env)
        assert result.exit_code != 0

    def test_unlink(self, runner):
        r, env = runner
        r.invoke(cli, ["create", "A"], env=env)
        r.invoke(cli, ["create", "B"], env=env)
        r.invoke(cli, ["link", "T-001", "blocks", "T-002"], env=env)
        result = r.invoke(cli, ["unlink", "T-001", "blocks", "T-002"], env=env)
        assert result.exit_code == 0
        assert "Unlinked" in result.output


class TestSprint:
    def test_sprint_create(self, runner):
        r, env = runner
        result = r.invoke(cli, ["sprint", "create", "Sprint 1"], env=env)
        assert result.exit_code == 0
        assert "sprint-1" in result.output

    def test_sprint_list(self, runner):
        r, env = runner
        r.invoke(cli, ["sprint", "create", "Sprint 1"], env=env)
        r.invoke(cli, ["sprint", "create", "Sprint 2"], env=env)
        result = r.invoke(cli, ["sprint", "list"], env=env)
        assert "sprint-1" in result.output
        assert "sprint-2" in result.output

    def test_sprint_list_empty(self, runner):
        r, env = runner
        result = r.invoke(cli, ["sprint", "list"], env=env)
        assert "No sprints" in result.output

    def test_sprint_add(self, runner):
        r, env = runner
        r.invoke(cli, ["sprint", "create", "S1"], env=env)
        r.invoke(cli, ["create", "T1"], env=env)
        r.invoke(cli, ["create", "T2"], env=env)
        result = r.invoke(cli, ["sprint", "add", "sprint-1", "T-001", "T-002"], env=env)
        assert result.exit_code == 0
        assert "T-001" in result.output
        assert "T-002" in result.output

    def test_sprint_complete(self, runner):
        r, env = runner
        r.invoke(cli, ["sprint", "create", "S1"], env=env)
        result = r.invoke(cli, ["sprint", "complete", "sprint-1"], env=env)
        assert result.exit_code == 0
        assert "Completed" in result.output

    def test_sprint_complete_nonexistent(self, runner):
        r, env = runner
        result = r.invoke(cli, ["sprint", "complete", "sprint-99"], env=env)
        assert result.exit_code != 0

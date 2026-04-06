# Diwan (ديوان)

Lightweight agent-first issue tracker. SQLite storage, MCP server for LLM access, TUI for humans, CLI for scripts. No Docker, no Redis, no PostgreSQL.

## Install

```bash
pip install -e .
```

## Usage

```bash
# Initialize in current directory
diwan init

# Create tickets
diwan create "Fix login bug" --priority high --labels "backend,bug"

# List and search
diwan list --status todo
diwan search "login"

# Update and comment
diwan update T-001 --status in_progress
diwan comment T-001 "Working on this now"

# Sprints
diwan sprint create "Sprint 1"
diwan sprint add sprint-1 T-001 T-002

# Dependencies
diwan link T-002 blocks T-001

# MCP server (for agents)
diwan mcp

# Terminal UI
diwan tui
```

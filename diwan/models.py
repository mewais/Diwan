"""Data models for Diwan."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Status(str, Enum):
    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    DONE = "done"
    CANCELLED = "cancelled"


class Priority(str, Enum):
    URGENT = "urgent"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class SprintStatus(str, Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    COMPLETED = "completed"


class LinkRelation(str, Enum):
    BLOCKS = "blocks"
    BLOCKED_BY = "blocked_by"
    RELATES_TO = "relates_to"
    PARENT_OF = "parent_of"
    CHILD_OF = "child_of"


@dataclass
class Ticket:
    id: str
    title: str
    description: str = ""
    status: Status = Status.BACKLOG
    priority: Priority = Priority.MEDIUM
    labels: list[str] = field(default_factory=list)
    assignee: str = ""
    sprint_id: Optional[str] = None
    parent_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @staticmethod
    def from_row(row: dict) -> Ticket:
        return Ticket(
            id=row["id"],
            title=row["title"],
            description=row["description"] or "",
            status=Status(row["status"]),
            priority=Priority(row["priority"]),
            labels=json.loads(row["labels"]) if row["labels"] else [],
            assignee=row["assignee"] or "",
            sprint_id=row["sprint_id"],
            parent_id=row["parent_id"],
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "labels": self.labels,
            "assignee": self.assignee,
            "sprint_id": self.sprint_id,
            "parent_id": self.parent_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class Comment:
    id: int
    ticket_id: str
    author: str
    content: str
    created_at: Optional[datetime] = None

    @staticmethod
    def from_row(row: dict) -> Comment:
        return Comment(
            id=row["id"],
            ticket_id=row["ticket_id"],
            author=row["author"] or "",
            content=row["content"],
            created_at=_parse_dt(row["created_at"]),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ticket_id": self.ticket_id,
            "author": self.author,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class Sprint:
    id: str
    name: str
    status: SprintStatus = SprintStatus.PLANNING
    created_at: Optional[datetime] = None

    @staticmethod
    def from_row(row: dict) -> Sprint:
        return Sprint(
            id=row["id"],
            name=row["name"],
            status=SprintStatus(row["status"]),
            created_at=_parse_dt(row["created_at"]),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class Link:
    from_id: str
    to_id: str
    relation: LinkRelation

    @staticmethod
    def from_row(row: dict) -> Link:
        return Link(
            from_id=row["from_id"],
            to_id=row["to_id"],
            relation=LinkRelation(row["relation"]),
        )

    def to_dict(self) -> dict:
        return {
            "from_id": self.from_id,
            "to_id": self.to_id,
            "relation": self.relation.value,
        }


def _parse_dt(val: Optional[str]) -> Optional[datetime]:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val)
    except (ValueError, TypeError):
        return None

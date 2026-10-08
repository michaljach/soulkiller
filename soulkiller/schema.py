"""Two record types everything is normalized into.

Message: one utterance in a conversation (email, chat, comment). Feeds fine-tuning + memory.
Doc:     a standalone piece of life data (file, note, event, post, day log). Feeds memory.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


@dataclass
class Message:
    source: str            # gmail, whatsapp, messenger, ...
    thread_id: str         # stable id of the conversation
    timestamp: str         # ISO 8601, UTC
    sender: str
    is_me: bool
    text: str
    thread_title: str = ""
    participants: list[str] = field(default_factory=list)


@dataclass
class Doc:
    source: str
    doc_id: str
    timestamp: str
    title: str
    text: str
    authored_by_me: bool = False
    meta: dict = field(default_factory=dict)


def iso(dt: datetime | float | int | None) -> str:
    if dt is None:
        return ""
    if isinstance(dt, (int, float)):
        # accept seconds or milliseconds
        dt = datetime.fromtimestamp(dt / 1000 if dt > 1e11 else dt, tz=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def write_jsonl(path: Path, records: Iterable) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(asdict(r) if hasattr(r, "__dataclass_fields__") else r, ensure_ascii=False) + "\n")
            n += 1
    return n


def read_jsonl(path: Path):
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)

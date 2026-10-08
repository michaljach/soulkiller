from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    name: str
    emails: set[str]
    names: set[str]
    raw: Path
    processed: Path
    skip_senders: list[str] = field(default_factory=list)
    min_chars: int = 2
    context_messages: int = 12
    max_chars_per_example: int = 6000

    def is_me(self, sender: str | None) -> bool:
        if not sender:
            return False
        s = sender.strip().lower()
        if s in self.emails or s in self.names:
            return True
        # "Name <addr@x>" form
        return any(e in s for e in self.emails)

    def is_skipped(self, sender: str | None) -> bool:
        s = (sender or "").lower()
        return any(p in s for p in self.skip_senders)


def load(path: str | Path = "config.toml") -> Config:
    path = Path(path)
    data = tomllib.loads(path.read_text())
    root = path.parent
    me, paths = data["me"], data.get("paths", {})
    filters, sft = data.get("filters", {}), data.get("sft", {})
    return Config(
        name=me["name"],
        emails={e.lower() for e in me.get("emails", [])},
        names={n.lower() for n in me.get("names", [])} | {me["name"].lower()},
        raw=root / paths.get("raw", "data/raw"),
        processed=root / paths.get("processed", "data/processed"),
        skip_senders=[s.lower() for s in filters.get("skip_senders", [])],
        min_chars=filters.get("min_chars", 2),
        context_messages=sft.get("context_messages", 12),
        max_chars_per_example=sft.get("max_chars_per_example", 6000),
    )

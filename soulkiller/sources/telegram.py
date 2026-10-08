"""Telegram Desktop -> Settings -> Export Telegram data (JSON) -> result.json"""
from __future__ import annotations

import json
from pathlib import Path

from ..clean import normalize, redact
from ..schema import Message, iso


def _text(t) -> str:
    if isinstance(t, str):
        return t
    return "".join(x if isinstance(x, str) else x.get("text", "") for x in t)


def ingest(cfg, root: Path):
    for path in sorted(root.rglob("result.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        me_id = f"user{data.get('personal_information', {}).get('user_id', '')}"
        chats = data.get("chats", {}).get("list", []) or [data]
        for chat in chats:
            title = chat.get("name") or str(chat.get("id"))
            for m in chat.get("messages", []):
                text = _text(m.get("text", ""))
                if m.get("type") != "message" or not text:
                    continue
                sender = m.get("from") or ""
                yield Message(
                    source="telegram", thread_id=str(chat.get("id")), timestamp=iso(int(m["date_unixtime"])) if m.get("date_unixtime") else m.get("date", ""),
                    sender=sender, is_me=m.get("from_id") == me_id or cfg.is_me(sender),
                    text=normalize(redact(text)), thread_title=title,
                )

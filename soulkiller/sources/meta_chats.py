"""Facebook Messenger + Instagram DMs (same JSON format), incl. Messenger E2EE app exports."""
from __future__ import annotations

import json
from pathlib import Path

from ..clean import fix_meta_encoding, normalize, redact
from ..schema import Message, iso


def _thread(cfg, source: str, thread_id: str, data: dict):
    title = fix_meta_encoding(data.get("title") or data.get("threadName") or thread_id)
    participants = [fix_meta_encoding(p.get("name", "") if isinstance(p, dict) else p)
                    for p in data.get("participants", [])]
    for m in data.get("messages", []):
        text = m.get("content") or m.get("text") or ""
        sender = m.get("sender_name") or m.get("senderName") or ""
        ts = m.get("timestamp_ms") or m.get("timestamp")
        if not text or m.get("is_unsent") or m.get("isUnsent"):
            continue
        text, sender = fix_meta_encoding(text), fix_meta_encoding(sender)
        # Auto-generated system lines ("You sent an attachment.", "reacted ❤ to your message")
        if text.endswith(" sent an attachment.") or " to your message" in text:
            continue
        yield Message(
            source=source, thread_id=thread_id, timestamp=iso(ts), sender=sender,
            is_me=cfg.is_me(sender), text=normalize(redact(text)),
            thread_title=title, participants=participants,
        )


def make_ingest(source: str):
    def ingest(cfg, root: Path):
        for path in sorted(root.rglob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            # Any JSON with a messages array: inbox/*/message_N.json and flat E2EE exports alike
            if not isinstance(data, dict) or not isinstance(data.get("messages"), list):
                continue
            thread_id = f"{path.parent.name}/{path.stem}" if path.parent != root else path.stem
            # message_1.json, message_2.json share one thread
            thread_id = thread_id.rsplit("/message_", 1)[0]
            yield from _thread(cfg, source, thread_id, data)
    return ingest


messenger = make_ingest("messenger")
instagram = make_ingest("instagram")

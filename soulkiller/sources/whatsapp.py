"""WhatsApp: per-chat 'Export chat' (without media) -> .txt files."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from ..clean import normalize, redact
from ..schema import Message, iso

# [12.03.2020, 14:22:01] Name: text      (iOS)
# 12.03.2020, 14:22 - Name: text         (Android, PL)
# 3/12/20, 2:22 PM - Name: text          (Android, US)
LINE_RE = re.compile(
    r"^‎?\[?(?P<date>\d{1,4}[./-]\d{1,2}[./-]\d{1,4}),? (?P<time>\d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap]\.?[Mm]\.?)?)\]?"
    r"(?: -|:)? (?P<sender>[^:]{1,80}): (?P<text>.*)$"
)
SYSTEM = ("<Media omitted>", "<Multimedia pominięte>", "image omitted", "video omitted", "sticker omitted",
          "audio omitted", "This message was deleted", "Ta wiadomość została usunięta", "<attached:")
DATE_FORMATS = ["%d.%m.%Y", "%d.%m.%y", "%d/%m/%Y", "%d/%m/%y", "%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d"]


def _parse_dt(d: str, t: str):
    t = t.replace(".", "").upper().replace(" ", "")
    tfmts = ["%H:%M:%S", "%H:%M"] if not t.endswith("M") else ["%I:%M:%S%p", "%I:%M%p"]
    for df in DATE_FORMATS:
        for tf in tfmts:
            try:
                return datetime.strptime(f"{d} {t}", f"{df} {tf}")
            except ValueError:
                pass
    return None


def ingest(cfg, root: Path):
    for path in sorted(root.rglob("*.txt")):
        thread = path.stem.removeprefix("WhatsApp Chat with ").removeprefix("Czat WhatsApp z ")
        msgs = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            m = LINE_RE.match(line)
            if m:
                msgs.append([m["sender"].strip("‎ "), _parse_dt(m["date"], m["time"]), m["text"]])
            elif msgs:  # continuation of a multi-line message
                msgs[-1][2] += "\n" + line
        participants = sorted({s for s, _, _ in msgs})
        for sender, dt, text in msgs:
            if any(s in text for s in SYSTEM):
                continue
            yield Message(
                source="whatsapp", thread_id=thread, timestamp=iso(dt), sender=sender,
                is_me=cfg.is_me(sender), text=normalize(redact(text)),
                thread_title=thread, participants=participants,
            )

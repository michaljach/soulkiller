"""Google Takeout -> Calendar -> *.ics"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from icalendar import Calendar

from ..schema import Doc, iso


def ingest(cfg, root: Path):
    for ics in sorted(root.rglob("*.ics")):
        cal = Calendar.from_ical(ics.read_bytes())
        for ev in cal.walk("VEVENT"):
            start = ev.get("DTSTART")
            start = start.dt if start else None
            if isinstance(start, date) and not isinstance(start, datetime):
                start = datetime(start.year, start.month, start.day)
            summary = str(ev.get("SUMMARY", "")).strip()
            if not summary:
                continue
            parts = [summary]
            for key in ("LOCATION", "DESCRIPTION"):
                if ev.get(key):
                    parts.append(f"{key.title()}: {ev.get(key)}")
            attendees = ev.get("ATTENDEE", [])
            attendees = attendees if isinstance(attendees, list) else [attendees]
            if attendees:
                parts.append("With: " + ", ".join(str(a).removeprefix("mailto:") for a in attendees))
            yield Doc(
                source="calendar",
                doc_id=str(ev.get("UID", summary)),
                timestamp=iso(start),
                title=summary,
                text="\n".join(parts),
                meta={"calendar": ics.stem},
            )

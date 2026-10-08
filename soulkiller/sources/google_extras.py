"""Lifelog from Google Takeout: YouTube history, Chrome history, Maps Timeline.

Rolled up into one Doc per day so memory can answer "what was I into in May 2021?"
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from ..schema import Doc, iso


def _youtube(root: Path, days):
    for path in root.rglob("watch-history.json"):
        for e in json.loads(path.read_text(encoding="utf-8")):
            title = e.get("title", "").removeprefix("Watched ").removeprefix("Obejrzano: ")
            if e.get("time") and title and not title.startswith("https://"):
                days[e["time"][:10]]["Watched on YouTube"].append(title)
    for path in root.rglob("search-history.json"):
        for e in json.loads(path.read_text(encoding="utf-8")):
            if e.get("time") and e.get("title"):
                days[e["time"][:10]]["Searched YouTube"].append(e["title"].split(" ", 1)[-1])


def _chrome(root: Path, days):
    for path in root.rglob("History.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        for e in data.get("Browser History", []):
            title, us = e.get("title"), e.get("time_usec")
            if title and us:
                days[iso(us / 1_000_000)[:10]]["Browsed"].append(title)


def _timeline(root: Path, days):
    # New on-device format (exported from phone): Timeline.json with semanticSegments
    for path in root.rglob("Timeline.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        for seg in data.get("semanticSegments", []):
            visit = seg.get("visit", {}).get("topCandidate", {})
            if visit and seg.get("startTime"):
                place = visit.get("semanticType") or visit.get("placeLocation", {}).get("latLng", "")
                days[seg["startTime"][:10]]["Visited"].append(str(place))
    # Legacy Takeout format: Semantic Location History/YYYY/YYYY_MONTH.json
    for path in root.rglob("Semantic Location History/**/*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        for obj in data.get("timelineObjects", []):
            pv = obj.get("placeVisit")
            if pv:
                loc = pv.get("location", {})
                ts = pv.get("duration", {}).get("startTimestamp", "")
                name = loc.get("name") or loc.get("address")
                if ts and name:
                    days[ts[:10]]["Visited"].append(name)


def ingest(cfg, root: Path):
    days = defaultdict(lambda: defaultdict(list))
    _youtube(root, days)
    _chrome(root, days)
    _timeline(root, days)
    for day in sorted(days):
        sections = []
        for kind, items in days[day].items():
            uniq = list(dict.fromkeys(items))[:60]
            sections.append(f"{kind}: " + "; ".join(uniq))
        yield Doc(source="lifelog", doc_id=day, timestamp=day + "T00:00:00+00:00", title=f"Activity on {day}",
                  text="\n".join(sections))

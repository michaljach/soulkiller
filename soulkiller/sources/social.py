"""Public-ish writing: X/Twitter, Reddit, LinkedIn, Facebook posts & comments."""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from ..clean import fix_meta_encoding, normalize, redact
from ..schema import Doc, Message, iso


def _js_array(path: Path):
    """X archive files look like: window.YTD.tweets.part0 = [ ... ]"""
    raw = path.read_text(encoding="utf-8")
    return json.loads(raw[raw.index("["):])


def twitter(cfg, root: Path):
    for path in sorted(root.rglob("tweet*.js")):
        if "deleted" in path.name:
            continue
        for item in _js_array(path):
            t = item.get("tweet", item)
            text = t.get("full_text") or t.get("text", "")
            if text.startswith("RT @"):
                continue  # retweets aren't my words
            ts = datetime.strptime(t["created_at"], "%a %b %d %H:%M:%S %z %Y")
            yield Doc(source="twitter", doc_id=t.get("id_str", ""), timestamp=iso(ts), title="Tweet",
                      text=normalize(text), authored_by_me=True,
                      meta={"reply_to": t.get("in_reply_to_screen_name")})
    my_ids = {a["account"]["accountId"] for p in root.rglob("account.js") for a in _js_array(p)}
    for path in sorted(root.rglob("direct-messages*.js")):
        for item in _js_array(path):
            conv = item["dmConversation"]
            for m in conv.get("messages", []):
                mc = m.get("messageCreate")
                if not mc:
                    continue
                yield Message(source="twitter_dm", thread_id=conv["conversationId"], timestamp=mc["createdAt"],
                              sender=mc["senderId"], is_me=mc["senderId"] in my_ids,
                              text=normalize(redact(mc.get("text", ""))))


def _csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def reddit(cfg, root: Path):
    for name, kind in (("comments.csv", "comment"), ("posts.csv", "post")):
        for path in root.rglob(name):
            for row in _csv(path):
                body = row.get("body") or ""
                title = row.get("title") or f"r/{row.get('subreddit', '')} {kind}"
                if body in {"", "[deleted]", "[removed]"} and kind == "comment":
                    continue
                yield Doc(source="reddit", doc_id=row.get("id", ""), timestamp=row.get("date", ""),
                          title=title, text=normalize(f"{title}\n\n{body}" if kind == "post" else body),
                          authored_by_me=True, meta={"subreddit": row.get("subreddit"), "kind": kind})


def linkedin(cfg, root: Path):
    for path in root.rglob("messages.csv"):
        for row in _csv(path):
            sender = row.get("FROM", "")
            yield Message(source="linkedin", thread_id=row.get("CONVERSATION ID", ""), timestamp=row.get("DATE", ""),
                          sender=sender, is_me=cfg.is_me(sender), text=normalize(redact(row.get("CONTENT", ""))),
                          thread_title=row.get("CONVERSATION TITLE") or row.get("SUBJECT", ""))
    for path in root.rglob("Shares.csv"):
        for row in _csv(path):
            if row.get("ShareCommentary"):
                yield Doc(source="linkedin", doc_id=row.get("ShareLink", ""), timestamp=row.get("Date", ""),
                          title="LinkedIn post", text=normalize(row["ShareCommentary"]), authored_by_me=True)
    for path in root.rglob("Profile.csv"):
        for row in _csv(path):
            text = "\n".join(f"{k}: {v}" for k, v in row.items() if v)
            yield Doc(source="linkedin", doc_id="profile", timestamp="", title="LinkedIn profile", text=text,
                      authored_by_me=True)
    for path in root.rglob("Positions.csv"):
        rows = list(_csv(path))
        text = "\n".join(f"{r.get('Title')} at {r.get('Company Name')} ({r.get('Started On')} – {r.get('Finished On') or 'now'}): "
                         f"{r.get('Description', '')}" for r in rows)
        yield Doc(source="linkedin", doc_id="positions", timestamp="", title="Career history", text=text,
                  authored_by_me=True)


def facebook_posts(cfg, root: Path):
    """Posts and comments (messages are handled by meta_chats.messenger)."""
    for path in sorted(root.rglob("*.json")):
        if "messages" in path.parts:
            continue
        name = path.name
        if not (name.startswith("your_posts") or name.startswith("comments")):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else data.get("comments_v2", [])
        for it in items:
            for d in it.get("data", []):
                text = d.get("post") or (d.get("comment") or {}).get("comment")
                if not text:
                    continue
                kind = "post" if "post" in d else "comment"
                yield Doc(source="facebook", doc_id=f"{kind}-{it.get('timestamp')}", timestamp=iso(it.get("timestamp")),
                          title=fix_meta_encoding(it.get("title", f"Facebook {kind}")),
                          text=normalize(fix_meta_encoding(text)), authored_by_me=True, meta={"kind": kind})

"""Build the fine-tuning dataset (chat format) from normalized records.

Each conversation session becomes one multi-turn example where *I* am the assistant.
Training masks loss to assistant turns, so the model learns my replies, not other people's text.
"""
from __future__ import annotations

import hashlib
import random
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from .schema import read_jsonl, write_jsonl

SESSION_GAP = {"gmail": timedelta(days=30)}       # an email thread is one conversation
DEFAULT_GAP = timedelta(hours=4)                  # chats: a pause this long starts a new session
CHANNEL = {"gmail": "email", "whatsapp": "WhatsApp", "messenger": "Messenger", "instagram": "Instagram DM",
           "telegram": "Telegram", "linkedin": "LinkedIn messages", "twitter_dm": "X DMs"}
WRITING_PROMPTS = {"twitter": "Write a tweet.", "reddit": "Write a Reddit {kind} in r/{subreddit}.",
                   "facebook": "Write a Facebook {kind}.", "linkedin": "Write a LinkedIn post."}


def system_prompt(name: str, channel: str, others: list[str], when: str) -> str:
    """Kept identical at inference time so the model can be steered by channel/person/date."""
    with_ = f" with {', '.join(others[:6])}" if others else ""
    return f"You are {name}. Conversation on {channel}{with_}. Date: {when}."


def _dt(ts: str):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _sessions(msgs: list[dict], gap: timedelta):
    session, last = [], None
    for m in msgs:
        t = _dt(m["timestamp"])
        if session and t and last and t - last > gap:
            yield session
            session = []
        session.append(m)
        last = t or last
    if session:
        yield session


def _turns(session: list[dict], group: bool):
    """Collapse consecutive messages from the same side into one turn so roles alternate."""
    turns = []  # [role, text]
    for m in session:
        role = "assistant" if m["is_me"] else "user"
        piece = f"{m['sender']}: {m['text']}" if group and role == "user" else m["text"]
        if turns and turns[-1][0] == role:
            turns[-1][1] += "\n" + piece
        else:
            turns.append([role, piece])
    return turns


def _chunk(turns, max_turns: int, max_chars: int):
    chunk, size = [], 0
    for turn in turns:
        if chunk and (len(chunk) >= max_turns or size + len(turn[1]) > max_chars) and chunk[-1][0] == "assistant":
            yield chunk
            chunk, size = [], 0
        chunk.append(turn)
        size += len(turn[1])
    if chunk:
        yield chunk


def conversation_examples(cfg):
    threads = defaultdict(list)
    for m in read_jsonl(cfg.processed / "messages.jsonl"):
        if len(m["text"]) >= cfg.min_chars:
            threads[(m["source"], m["thread_id"])].append(m)
    for (source, thread_id), msgs in threads.items():
        if not any(m["is_me"] for m in msgs):
            continue
        msgs.sort(key=lambda m: m["timestamp"])
        others = sorted({m["sender"] for m in msgs if not m["is_me"]})
        group = len(others) > 1
        for session in _sessions(msgs, SESSION_GAP.get(source, DEFAULT_GAP)):
            turns = _turns(session, group)
            for chunk in _chunk(turns, cfg.context_messages * 2, cfg.max_chars_per_example):
                if not any(t[0] == "assistant" for t in chunk):
                    continue
                while chunk and chunk[-1][0] == "user":  # must end on my reply
                    chunk.pop()
                first = session[0]
                when = first["timestamp"][:10]
                topic = f" Subject: \"{first['thread_title']}\"" if source == "gmail" and first["thread_title"] else ""
                messages = [{"role": "system",
                             "content": system_prompt(cfg.name, CHANNEL.get(source, source), others, when) + topic}]
                if chunk[0][0] == "assistant":  # I started it
                    messages.append({"role": "user", "content": "(you start the conversation)"})
                messages += [{"role": r, "content": text} for r, text in chunk]
                yield thread_id, source, messages


def writing_examples(cfg):
    for d in read_jsonl(cfg.processed / "docs.jsonl"):
        tmpl = WRITING_PROMPTS.get(d["source"])
        if not d["authored_by_me"] or not tmpl or len(d["text"]) < 20:
            continue
        meta = {"kind": "post", "subreddit": "", **{k: v for k, v in d["meta"].items() if v}}
        prompt = tmpl.format(**meta)
        yield d["doc_id"], d["source"], [
            {"role": "system", "content": system_prompt(cfg.name, d["source"], [], d["timestamp"][:10])},
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": d["text"]},
        ]


def build_sft(cfg, val_fraction: float = 0.03, seed: int = 0):
    seen, train, val, per_source = set(), [], [], Counter()
    for key, source, messages in [*conversation_examples(cfg), *writing_examples(cfg)]:
        digest = hashlib.sha1(repr(messages[1:]).encode()).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        per_source[source] += 1
        # split by thread so validation measures generalization, not memorization
        bucket = int(hashlib.md5(f"{source}/{key}".encode()).hexdigest(), 16) % 1000
        (val if bucket < val_fraction * 1000 else train).append({"messages": messages, "source": source})
    random.Random(seed).shuffle(train)
    n_train = write_jsonl(cfg.processed / "sft_train.jsonl", train)
    n_val = write_jsonl(cfg.processed / "sft_val.jsonl", val)
    return n_train, n_val, per_source

"""Google Takeout -> Mail -> *.mbox"""
from __future__ import annotations

import mailbox
from email.header import decode_header, make_header
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from pathlib import Path

from ..clean import html_to_text, normalize, redact, strip_quotes
from ..schema import Message, iso

SKIP_LABELS = {"spam", "trash", "kosz"}


def _hdr(msg, name: str) -> str:
    raw = msg.get(name)
    if not raw:
        return ""
    try:
        return str(make_header(decode_header(raw)))
    except Exception:
        return str(raw)


def _body(msg) -> str:
    plain, html = None, None
    for part in msg.walk() if msg.is_multipart() else [msg]:
        if part.get_content_maintype() == "multipart" or part.get_filename():
            continue
        ctype = part.get_content_type()
        try:
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        except (LookupError, AssertionError):
            continue
        if ctype == "text/plain" and plain is None:
            plain = text
        elif ctype == "text/html" and html is None:
            html = text
    if plain:
        return plain
    return html_to_text(html) if html else ""


def ingest(cfg, root: Path):
    for mbox_path in sorted(root.rglob("*.mbox")):
        for msg in mailbox.mbox(str(mbox_path), create=False):
            labels = {l.strip().lower() for l in _hdr(msg, "X-Gmail-Labels").split(",")}
            if labels & SKIP_LABELS:
                continue
            sender_name, sender_addr = parseaddr(_hdr(msg, "From"))
            is_me = sender_addr.lower() in cfg.emails
            # Bulk/automated mail is noise for both voice and memory
            if not is_me and (msg.get("List-Unsubscribe") or msg.get("Precedence", "").lower() in {"bulk", "list"}
                              or cfg.is_skipped(sender_addr)):
                continue
            text = normalize(redact(strip_quotes(_body(msg))))
            if len(text) < cfg.min_chars:
                continue
            try:
                ts = iso(parsedate_to_datetime(msg["Date"]))
            except Exception:
                ts = ""
            recipients = [a for _, a in getaddresses(msg.get_all("To", []) + msg.get_all("Cc", [])) if a]
            yield Message(
                source="gmail",
                thread_id=msg.get("X-GM-THRID") or _hdr(msg, "Subject"),
                timestamp=ts,
                sender=sender_name or sender_addr,
                is_me=is_me,
                text=text,
                thread_title=_hdr(msg, "Subject"),
                participants=sorted({sender_addr, *recipients}),
            )

"""Text cleanup: strip quoted replies/signatures, redact secrets, fix export encodings."""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

# Lines that introduce a quoted reply (English + Polish + common clients)
_REPLY_HEADERS = [
    r"^On .{5,200}wrote:\s*$",
    r"^W dniu .{5,200}(napisał|napisała|pisze)\S*:?\s*$",
    r"^\S+ .{0,100}(napisał|napisała)\S*:\s*$",
    r"^-{2,}\s*Original Message\s*-{2,}",
    r"^-{2,}\s*Wiadomość oryginalna\s*-{2,}",
    r"^-{2,}\s*Forwarded message\s*-{2,}",
    r"^-{2,}\s*Przekazana wiadomość\s*-{2,}",
    r"^From: .+$",
    r"^Od: .+$",
    r"^Sent from my \w+",
    r"^Wysłano z (mojego )?\w+",
    r"^_{10,}$",
]
_REPLY_RE = re.compile("|".join(_REPLY_HEADERS), re.IGNORECASE | re.MULTILINE)
_SIG_RE = re.compile(r"^-- ?$", re.MULTILINE)

_REDACTIONS = [
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[CARD]"),                                   # card-like numbers
    (re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}\b"), "[IBAN]"),                  # IBAN
    (re.compile(r"\b\d{11}\b"), "[PESEL]"),                                               # PESEL
    (re.compile(r"(?i)\b(password|hasło|haslo|pass|pwd|pin)\s*[:=]\s*\S+"), r"\1: [SECRET]"),
    (re.compile(r"(?i)\b(code|kod)\s*(is|to|:)?\s*\d{4,8}\b"), r"\1 [OTP]"),
    (re.compile(r"\b(sk|pk|ghp|gho|xox[bap])[-_][A-Za-z0-9_-]{16,}\b"), "[API_KEY]"),
]


def strip_quotes(text: str) -> str:
    """Keep only the newly written part of an email body."""
    m = _REPLY_RE.search(text)
    if m:
        text = text[: m.start()]
    m = _SIG_RE.search(text)
    if m:
        text = text[: m.start()]
    lines = [l for l in text.splitlines() if not l.lstrip().startswith(">")]
    return "\n".join(lines).strip()


def redact(text: str) -> str:
    for pat, repl in _REDACTIONS:
        text = pat.sub(repl, text)
    return text


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["style", "script", "head"]):
        tag.decompose()
    # Gmail wraps quoted history in these
    for tag in soup.select("blockquote, .gmail_quote, .gmail_extra, #appendonsend"):
        tag.decompose()
    return re.sub(r"\n{3,}", "\n\n", soup.get_text("\n")).strip()


def fix_meta_encoding(s: str) -> str:
    """Facebook/Instagram exports encode UTF-8 bytes as latin-1 code points (ą -> \\u00c4\\u0085)."""
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace(" ", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()

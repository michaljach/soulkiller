import json
import textwrap
from pathlib import Path

import pytest

from soulkiller import config as config_mod
from soulkiller.build import build_sft
from soulkiller.clean import fix_meta_encoding, redact, strip_quotes
from soulkiller.schema import read_jsonl, write_jsonl
from soulkiller.sources import SOURCES

MBOX = textwrap.dedent("""\
    From 1@xxx Mon Mar 04 10:00:00 2019
    X-GM-THRID: 111
    X-Gmail-Labels: Inbox
    From: Anna Nowak <anna@example.com>
    To: Test Me <me@example.com>
    Subject: Weekend?
    Date: Mon, 04 Mar 2019 10:00:00 +0000
    Content-Type: text/plain; charset=utf-8

    Cześć, jedziemy w góry w sobotę?

    From 2@xxx Mon Mar 04 11:00:00 2019
    X-GM-THRID: 111
    X-Gmail-Labels: Sent
    From: Test Me <me@example.com>
    To: Anna Nowak <anna@example.com>
    Subject: Re: Weekend?
    Date: Mon, 04 Mar 2019 11:00:00 +0000
    Content-Type: text/plain; charset=utf-8

    Jasne, biorę namiot. Hasło: tajne123

    W dniu 04.03.2019 o 10:00 Anna Nowak napisała:
    > Cześć, jedziemy w góry w sobotę?

    From 3@xxx Mon Mar 04 12:00:00 2019
    X-GM-THRID: 222
    From: Shop <noreply@shop.com>
    List-Unsubscribe: <mailto:x@shop.com>
    Subject: SALE
    Date: Mon, 04 Mar 2019 12:00:00 +0000
    Content-Type: text/plain

    Buy now!
    """)

WHATSAPP = textwrap.dedent("""\
    12.03.2020, 14:22 - Marek: siema, co tam?
    12.03.2020, 14:23 - Test Me: spoko, koduję
    i piję kawę
    12.03.2020, 14:23 - Test Me: <Multimedia pominięte>
    12.03.2020, 14:30 - Marek: nice
    """)

ICS = textwrap.dedent("""\
    BEGIN:VCALENDAR
    VERSION:2.0
    BEGIN:VEVENT
    UID:ev1
    DTSTART:20210515T090000Z
    SUMMARY:Wedding of Kasia
    LOCATION:Kraków
    END:VEVENT
    END:VCALENDAR
    """)


@pytest.fixture
def cfg(tmp_path):
    (tmp_path / "config.toml").write_text(textwrap.dedent("""\
        [me]
        name = "Test Me"
        emails = ["me@example.com"]
        names = ["Test Me", "testme"]
        [filters]
        skip_senders = ["noreply"]
        """))
    raw = tmp_path / "data/raw"
    (raw / "google/Takeout/Mail").mkdir(parents=True)
    (raw / "google/Takeout/Mail/All mail.mbox").write_text(MBOX)
    (raw / "google/Takeout/Calendar").mkdir(parents=True)
    (raw / "google/Takeout/Calendar/me.ics").write_text(ICS)
    (raw / "whatsapp").mkdir()
    (raw / "whatsapp/WhatsApp Chat with Marek.txt").write_text(WHATSAPP)
    inbox = raw / "facebook/your_activity/messages/inbox/kasia_123"
    inbox.mkdir(parents=True)
    mojibake = "zażółć".encode("utf-8").decode("latin-1")
    (inbox / "message_1.json").write_text(json.dumps({
        "participants": [{"name": "Kasia"}, {"name": "Test Me"}], "title": "Kasia",
        "messages": [  # Messenger exports newest first
            {"sender_name": "Test Me", "timestamp_ms": 1600000060000, "content": mojibake},
            {"sender_name": "Kasia", "timestamp_ms": 1600000000000, "content": "hej"},
        ]}))
    (raw / "telegram").mkdir()
    (raw / "telegram/result.json").write_text(json.dumps({
        "personal_information": {"user_id": 42},
        "chats": {"list": [{"id": 7, "name": "Bob", "messages": [
            {"type": "message", "from": "Bob", "from_id": "user9", "date": "2022-01-01T10:00:00",
             "date_unixtime": "1641031200", "text": ["see ", {"type": "link", "text": "this"}]},
            {"type": "message", "from": "Me Alias", "from_id": "user42", "date": "2022-01-01T10:01:00",
             "date_unixtime": "1641031260", "text": "cool"},
        ]}]}}))
    return config_mod.load(tmp_path / "config.toml")


def ingest_all(cfg):
    msgs, docs = [], []
    for folder, fn in SOURCES.values():
        root = cfg.raw / folder
        if root.exists():
            for r in fn(cfg, root):
                (docs if hasattr(r, "doc_id") else msgs).append(r)
    write_jsonl(cfg.processed / "messages.jsonl", msgs)
    write_jsonl(cfg.processed / "docs.jsonl", docs)
    return msgs, docs


def test_clean():
    assert strip_quotes("ok\n\nOn Mon, Bob wrote:\n> hi") == "ok"
    assert fix_meta_encoding("Å¼Ã³Å\x82w") == "żółw"
    assert "[SECRET]" in redact("hasło: abc123")
    assert "[CARD]" in redact("4111 1111 1111 1111")


def test_ingest(cfg):
    msgs, docs = ingest_all(cfg)
    gmail = [m for m in msgs if m.source == "gmail"]
    assert len(gmail) == 2, "newsletter must be dropped"
    mine = next(m for m in gmail if m.is_me)
    assert mine.text.startswith("Jasne, biorę namiot") and "napisała" not in mine.text and "tajne123" not in mine.text

    wa = [m for m in msgs if m.source == "whatsapp"]
    assert [m.text for m in wa] == ["siema, co tam?", "spoko, koduję\ni piję kawę", "nice"]
    assert wa[1].is_me and wa[1].timestamp.startswith("2020-03-12")

    fb = [m for m in msgs if m.source == "messenger"]
    assert {m.text for m in fb} == {"hej", "zażółć"} and fb[0].thread_id == "kasia_123"

    tg = [m for m in msgs if m.source == "telegram"]
    assert tg[0].text == "see this" and tg[1].is_me  # matched by user id, not display name

    assert any(d.source == "calendar" and "Kraków" in d.text for d in docs)


def test_build(cfg):
    ingest_all(cfg)
    n_train, n_val, per_source = build_sft(cfg, val_fraction=0)
    rows = list(read_jsonl(cfg.processed / "sft_train.jsonl"))
    assert n_train == len(rows) == 4
    for r in rows:
        roles = [m["role"] for m in r["messages"]]
        assert roles[0] == "system" and roles[-1] == "assistant"
        assert all(a != b for a, b in zip(roles[1:], roles[2:])), roles  # alternating
    wa = next(r for r in rows if r["source"] == "whatsapp")["messages"]
    assert [m["role"] for m in wa] == ["system", "user", "assistant"]  # trailing reply from Marek dropped
    assert "WhatsApp with Marek" in wa[0]["content"]

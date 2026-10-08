from __future__ import annotations

import argparse
import shutil
from collections import Counter
from pathlib import Path

from . import config as config_mod
from .build import build_sft
from .schema import Doc, Message, read_jsonl, write_jsonl
from .sources import SOURCES


def cmd_init(args):
    if not Path(args.config).exists():
        shutil.copy("config.example.toml", args.config)
        print(f"created {args.config}  <- fill in your name, emails and chat display names")
    cfg = config_mod.load(args.config)
    for folder in sorted({f for f, _ in SOURCES.values()}):
        (cfg.raw / folder).mkdir(parents=True, exist_ok=True)
    print(f"export folders ready under {cfg.raw}/")


def cmd_ingest(args):
    cfg = config_mod.load(args.config)
    only = set(args.only or SOURCES)
    messages, docs = [], []
    # keep records from sources not re-ingested this run
    for name, bucket, cls in (("messages", messages, Message), ("docs", docs, Doc)):
        path = cfg.processed / f"{name}.jsonl"
        if path.exists() and args.only:
            bucket += [r for r in read_jsonl(path) if r["source"] not in only and not
                       (r["source"] == "twitter_dm" and "twitter" in only)]
    for name, (folder, fn) in SOURCES.items():
        root = cfg.raw / folder
        if name not in only or not root.exists() or not any(root.iterdir()):
            continue
        n0 = len(messages) + len(docs)
        for rec in fn(cfg, root):
            (messages if isinstance(rec, Message) else docs).append(rec)
        print(f"{name:10s} {len(messages) + len(docs) - n0:>9,} records")
    write_jsonl(cfg.processed / "messages.jsonl", messages)
    write_jsonl(cfg.processed / "docs.jsonl", docs)
    print(f"-> {cfg.processed}/messages.jsonl, docs.jsonl")


def cmd_stats(args):
    cfg = config_mod.load(args.config)
    rows = Counter()
    for m in read_jsonl(cfg.processed / "messages.jsonl"):
        rows[(m["source"], "mine" if m["is_me"] else "others")] += len(m["text"])
        rows[(m["source"], "count")] += 1
    for d in read_jsonl(cfg.processed / "docs.jsonl"):
        rows[(d["source"], "mine" if d["authored_by_me"] else "others")] += len(d["text"])
        rows[(d["source"], "count")] += 1
    print(f"{'source':12s} {'records':>10s} {'my tokens':>12s} {'other tokens':>13s}")
    for src in sorted({s for s, _ in rows}):
        print(f"{src:12s} {rows[(src, 'count')]:>10,} {rows[(src, 'mine')] // 4:>12,} {rows[(src, 'others')] // 4:>13,}")
    mine = sum(v for (s, k), v in rows.items() if k == "mine") // 4
    print(f"\n~{mine:,} tokens written by you (rough: chars/4). "
          "Under ~200k: voice will be thin. 1M+: strong.")
    unknown = Counter(m["sender"] for m in read_jsonl(cfg.processed / "messages.jsonl")
                      if not m["is_me"] and m["source"] != "gmail")
    print("\nTop chat senders NOT recognized as you (add your aliases to config [me].names if listed):")
    for s, n in unknown.most_common(8):
        print(f"  {n:>7,}  {s}")


def cmd_build(args):
    cfg = config_mod.load(args.config)
    n_train, n_val, per_source = build_sft(cfg)
    print(f"train {n_train:,}  val {n_val:,}")
    for s, n in per_source.most_common():
        print(f"  {s:12s} {n:,}")
    print(f"-> {cfg.processed}/sft_train.jsonl  (copy to the GPU box)")


def main():
    p = argparse.ArgumentParser(prog="soulkiller")
    p.add_argument("--config", default="config.toml")
    sub = p.add_subparsers(required=True)
    sub.add_parser("init", help="create config + export folders").set_defaults(fn=cmd_init)
    s = sub.add_parser("ingest", help="parse raw exports into normalized JSONL")
    s.add_argument("--only", nargs="*", choices=list(SOURCES))
    s.set_defaults(fn=cmd_ingest)
    sub.add_parser("stats", help="how much of you is in the data").set_defaults(fn=cmd_stats)
    sub.add_parser("build", help="build fine-tuning dataset").set_defaults(fn=cmd_build)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

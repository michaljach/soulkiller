"""Commit messages I authored, from local repos listed in data/raw/git/repos.txt (one path per line)."""
from __future__ import annotations

import subprocess
from pathlib import Path

from ..schema import Doc


def ingest(cfg, root: Path):
    listing = root / "repos.txt"
    if not listing.exists():
        return
    authors = [f"--author={e}" for e in cfg.emails]
    for repo in filter(None, (l.strip() for l in listing.read_text().splitlines())):
        out = subprocess.run(
            ["git", "-C", repo, "log", "--all", *authors, "--format=%H%x1f%aI%x1f%B%x1e"],
            capture_output=True, text=True,
        ).stdout
        for rec in out.split("\x1e"):
            parts = rec.strip().split("\x1f")
            if len(parts) == 3 and parts[2].strip():
                yield Doc(source="git", doc_id=parts[0], timestamp=parts[1], title=f"Commit in {Path(repo).name}",
                          text=parts[2].strip(), authored_by_me=True, meta={"repo": repo})

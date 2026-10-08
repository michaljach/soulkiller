"""Documents: Google Drive (Takeout exports Docs as .docx) and notes folders (Obsidian, Markdown)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..clean import normalize, redact
from ..schema import Doc, iso

MAX_CHARS = 200_000


def _read(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".markdown", ".org", ".csv"}:
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".docx":
        import docx
        return "\n".join(p.text for p in docx.Document(str(path)).paragraphs)
    if suffix == ".pdf":
        from pypdf import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages[:200])
    if suffix in {".html", ".htm"}:
        from ..clean import html_to_text
        return html_to_text(path.read_text(encoding="utf-8", errors="replace"))
    return ""


def make_ingest(source: str, authored_by_me: bool):
    def ingest(cfg, root: Path):
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            if any(part.startswith(".") for part in path.relative_to(root).parts):
                continue
            try:
                text = _read(path)
            except Exception as e:  # corrupt files are common in old archives
                print(f"  skip {path.name}: {e}")
                continue
            text = normalize(redact(text))[:MAX_CHARS]
            if len(text) < 20:
                continue
            yield Doc(
                source=source,
                doc_id=str(path.relative_to(root)),
                timestamp=iso(datetime.fromtimestamp(path.stat().st_mtime)),
                title=path.stem,
                text=text,
                authored_by_me=authored_by_me,
            )
    return ingest


_drive_files = make_ingest("drive", authored_by_me=False)
DRIVE_DIRS = {"drive", "dysk"}  # Takeout folder names follow the account language


def drive(cfg, root: Path):
    for d in root.rglob("*"):
        if d.is_dir() and d.name.lower() in DRIVE_DIRS:
            yield from _drive_files(cfg, d)
notes = make_ingest("notes", authored_by_me=True)

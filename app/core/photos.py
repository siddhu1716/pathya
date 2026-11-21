"""Photos the family scanned (plates, prescriptions, strips, reports), kept so they can look at them again.
They are health data: stored only on this server in PHOTOS_DIR (gitignored, never committed, AGENTS.md rule 10) and
served only through the key-protected API."""
import os
import re
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/heic": ".heic", "image/heif": ".heif"}
MEDIA = {v: k for k, v in TYPES.items()}
ID = re.compile(r"^[0-9a-f]{20}$")


def folder():
    d = Path(os.getenv("PHOTOS_DIR", ROOT / "photos"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def save(data: bytes, mime: str) -> str | None:
    ext = TYPES.get((mime or "").lower())
    if not ext or not data:
        return None
    pid = uuid.uuid4().hex[:20]
    (folder() / f"{pid}{ext}").write_bytes(data)
    return pid


def find(pid: str):
    """(path, media type) of a stored photo, or None. Only our own ids, so no path tricks."""
    if not ID.match(pid or ""):
        return None
    for ext, media in MEDIA.items():
        p = folder() / f"{pid}{ext}"
        if p.is_file():
            return p, media
    return None

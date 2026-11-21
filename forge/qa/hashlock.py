"""sha256 of the files a QA report vouches for."""

from __future__ import annotations

import hashlib
from pathlib import Path

LOCKED_FILES = {"interior": "interior.pdf", "cover": "cover.pdf", "manifest": "manifest.json"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def file_hashes(out_dir: Path) -> dict[str, str | None]:
    return {
        k: sha256_file(out_dir / name) if (out_dir / name).is_file() else None
        for k, name in LOCKED_FILES.items()
    }


def is_stale(locked: dict[str, str | None], out_dir: Path) -> bool:
    return file_hashes(out_dir) != locked

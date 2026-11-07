"""migrate / backup / restore for an installed Puzzle Forge (forge migrate|backup|restore)."""

from __future__ import annotations

import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from forge.config import Settings

# (version, SQL) applied in order; tables themselves are created by their stores (CREATE IF NOT
# EXISTS), so only ALTERs / data fixes go here.
MIGRATIONS: list[tuple[int, str]] = [
    (1, "-- baseline: registry, book states, jobs, AI ledger/cache, vault outbox"),
]
KEEP = 14


def migrate(st: Settings) -> int:
    """Create every table, apply pending migrations; returns the schema version."""
    from forge.ai.ledger import Ledger
    from forge.core.registry import Registry
    from forge.jobs import JobQueue
    from forge.qa.state import StateStore
    from forge.vault.sync import VaultOutbox

    st.db_path.parent.mkdir(parents=True, exist_ok=True)
    with Registry(st.db_path):
        pass
    with StateStore(st.db_path):
        pass
    for store in (JobQueue(st.db_path), Ledger(st.db_path), VaultOutbox(st.db_path)):
        store.close()
    c = sqlite3.connect(st.db_path)
    try:
        c.execute(
            "CREATE TABLE IF NOT EXISTS forge_schema (version INTEGER PRIMARY KEY, "
            "applied_at TEXT NOT NULL)"
        )
        done = {r[0] for r in c.execute("SELECT version FROM forge_schema")}
        for version, sql in MIGRATIONS:
            if version not in done:
                with c:
                    c.executescript(sql)
                    c.execute(
                        "INSERT INTO forge_schema VALUES (?, ?)",
                        (version, datetime.now(UTC).isoformat()),
                    )
        return int(c.execute("SELECT COALESCE(MAX(version), 0) FROM forge_schema").fetchone()[0])
    finally:
        c.close()


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def backup(st: Settings, dest: Path | None = None, upload: bool = True) -> list[Path]:
    """data archive (db snapshot + output) and config archive (forge.env, secrets, overrides).

    Both are mode 600. Upload (rclone, FORGE_BACKUP_REMOTE) sends the data archive; the config
    archive holds the secret key and is uploaded only with FORGE_BACKUP_INCLUDE_SECRETS=1
    (then use an rclone *crypt* remote)."""
    import os

    dest = dest or st.data_dir / "backups"
    dest.mkdir(parents=True, exist_ok=True)
    ts = _stamp()
    out: list[Path] = []
    with tempfile.TemporaryDirectory() as tmp:
        snap = Path(tmp) / "forge.db"
        if st.db_path.is_file():
            src = sqlite3.connect(st.db_path)
            dst = sqlite3.connect(snap)
            src.backup(dst)  # consistent online copy
            dst.close()
            src.close()
        data_tar = dest / f"forge-data-{ts}.tar.gz"
        with tarfile.open(data_tar, "w:gz") as t:
            if snap.exists():
                t.add(snap, arcname="data/forge.db")
            if st.output_dir.is_dir():
                t.add(st.output_dir, arcname="output")
        out.append(data_tar)
    cfg_tar = dest / f"forge-config-{ts}.tar.gz"
    with tarfile.open(cfg_tar, "w:gz") as t:
        if st.config_file.is_file():
            t.add(st.config_file, arcname="config/forge.env")
        if st.config_dir.is_dir():
            for p in sorted(st.config_dir.iterdir()):
                if p.is_file() and p.name != "forge.env":
                    t.add(p, arcname=f"config/{p.name}")
    out.append(cfg_tar)
    for p in out:
        p.chmod(0o600)
    for prefix in ("forge-data-", "forge-config-"):
        for old in sorted(dest.glob(f"{prefix}*.tar.gz"))[:-KEEP]:
            old.unlink()
    if upload and st.backup_remote:
        send = out if os.environ.get("FORGE_BACKUP_INCLUDE_SECRETS") == "1" else out[:1]
        for p in send:
            subprocess.run(["rclone", "copy", str(p), st.backup_remote], check=True, timeout=7200)
    return out


def _extract(archive: Path, prefix: str, target: Path) -> int:
    n = 0
    with tarfile.open(archive, "r:gz") as t:
        for m in t.getmembers():
            if not m.name.startswith(prefix + "/") or not m.isfile():
                continue
            rel = Path(m.name).relative_to(prefix)
            if ".." in rel.parts:
                raise ValueError(f"unsafe path in archive: {m.name}")
            dst = target / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            src = t.extractfile(m)
            assert src is not None
            with src, dst.open("wb") as fh:
                shutil.copyfileobj(src, fh)
            n += 1
    return n


def restore(st: Settings, data_archive: Path | None, config_archive: Path | None) -> dict[str, int]:
    """Stop services first (the `forge restore` wrapper does). Existing files are overwritten."""
    res = {}
    if data_archive:
        res["data"] = _extract(data_archive, "data", st.db_path.parent)
        res["output"] = _extract(data_archive, "output", st.output_dir)
    if config_archive:
        res["config"] = _extract(config_archive, "config", st.config_dir)
        env = st.config_dir / "forge.env"
        if env.is_file() and st.config_file != env:
            shutil.move(env, st.config_file)
        for p in st.config_dir.iterdir():
            p.chmod(0o600)
    return res

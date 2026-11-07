"""P10.5: installer, wrapper, systemd units, migrate / backup / restore."""

from __future__ import annotations

import subprocess
import tarfile

from forge.config import REPO_ROOT, get_settings
from forge.maintenance import backup, migrate, restore

SCRIPTS = REPO_ROOT / "scripts"


def test_scripts_parse():
    for name in ("install.sh", "forge-wrapper.sh", "smoke_test.sh"):
        assert subprocess.run(["bash", "-n", str(SCRIPTS / name)]).returncode == 0, name
    help_text = subprocess.run(
        ["bash", str(SCRIPTS / "install.sh"), "--help"], capture_output=True, text=True
    ).stdout
    assert "/opt/puzzle-forge" in help_text


def test_systemd_units():
    web = (SCRIPTS / "systemd" / "forge-web.service").read_text()
    assert "User=forge" in web and "EnvironmentFile=/etc/puzzle-forge/forge.env" in web
    assert "ProtectSystem=strict" in web and "forge web run" in web
    assert "forge worker" in (SCRIPTS / "systemd" / "forge-worker.service").read_text()
    assert "OnCalendar" in (SCRIPTS / "systemd" / "forge-backup.timer").read_text()
    wrapper = (SCRIPTS / "forge-wrapper.sh").read_text()
    for verb in ("update)", "restore)", "logs)", "restart)", "smoke)"):
        assert verb in wrapper


def _env(tmp_path, monkeypatch):
    cfg = tmp_path / "etc" / "forge.env"
    cfg.parent.mkdir()
    cfg.write_text("FORGE_ENV=test\n")
    monkeypatch.setenv("FORGE_CONFIG", str(cfg))
    monkeypatch.setenv("FORGE_DATA_DIR", str(tmp_path / "var"))
    monkeypatch.setenv("FORGE_CONFIG_DIR", str(tmp_path / "etc"))
    for k in ("FORGE_DB_PATH", "FORGE_OUTPUT_DIR", "FORGE_BACKUP_REMOTE"):
        monkeypatch.delenv(k, raising=False)
    return get_settings()


def test_migrate_backup_restore_roundtrip(tmp_path, monkeypatch):
    st = _env(tmp_path, monkeypatch)
    assert migrate(st) == 1 and migrate(st) == 1  # idempotent
    from forge.jobs import JobQueue
    from forge.secrets import SecretStore

    q = JobQueue(st.db_path)
    q.add("vault_sync", {}, "before backup")
    q.close()
    (st.output_dir / "bk-1").mkdir(parents=True)
    (st.output_dir / "bk-1" / "interior.pdf").write_bytes(b"%PDF-1.7 x")
    SecretStore(st.config_dir).set("OPENAI_API_KEY", "sk-keep-me-123456")
    data_tar, cfg_tar = backup(st, upload=False)
    assert oct(data_tar.stat().st_mode & 0o777) == "0o600"
    with tarfile.open(data_tar) as t:
        names = t.getnames()
    assert "data/forge.db" in names and "output/bk-1/interior.pdf" in names
    with tarfile.open(cfg_tar) as t:
        assert "config/secret.key" in t.getnames()
    assert "secret" not in " ".join(names)  # the data archive never holds secrets
    # disaster: everything gone
    import shutil

    shutil.rmtree(st.data_dir / "data")
    shutil.rmtree(st.output_dir)
    for p in st.config_dir.iterdir():
        p.unlink()
    res = restore(st, data_tar, cfg_tar)
    assert res["output"] == 1 and res["config"] >= 2
    q = JobQueue(st.db_path)
    assert q.recent()[0].title == "before backup"
    q.close()
    assert SecretStore(st.config_dir).get("OPENAI_API_KEY") == "sk-keep-me-123456"
    assert st.config_file.read_text().startswith("FORGE_ENV=test")


def test_backup_keeps_14(tmp_path, monkeypatch):
    st = _env(tmp_path, monkeypatch)
    migrate(st)
    d = st.data_dir / "backups"
    d.mkdir(parents=True)
    for i in range(20):
        (d / f"forge-data-2026010{i:02d}.tar.gz").write_text("x")
    backup(st, upload=False)
    assert len(list(d.glob("forge-data-*.tar.gz"))) == 14


def test_install_into_fake_root(tmp_path):
    """install.sh against a throw-away root: dirs, forge.env (600), release from a git tag."""
    import os
    import shutil

    if shutil.which("git") is None:
        return
    repo = tmp_path / "src"
    skip = shutil.ignore_patterns(
        ".git",
        ".venv",
        "output",
        "data",
        "review",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        "apps",
    )
    shutil.copytree(REPO_ROOT, repo, ignore=skip)
    shutil.copytree(REPO_ROOT / "apps", repo / "apps", ignore=skip)
    git = ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-qm", "snapshot"], check=True)
    subprocess.run([*git, "tag", "v9.9.9"], check=True)
    root = tmp_path / "root"
    env = {**os.environ, "FORGE_INSTALL_ROOT": str(root), "SKIP_APT": "1", "NO_SYSTEMD": "1"}
    r = subprocess.run(
        ["bash", str(repo / "scripts" / "install.sh"), "--env", "test"],
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    conf = root / "etc" / "puzzle-forge" / "forge.env"
    assert oct(conf.stat().st_mode & 0o777) == "0o600"
    assert "FORGE_ENV=test" in conf.read_text()
    cur = root / "opt" / "puzzle-forge" / "current"
    assert (cur / "BUILD_INFO").read_text().startswith("version=9.9.9")
    assert (root / "usr" / "local" / "bin" / "forge").is_file()
    assert (root / "var" / "lib" / "puzzle-forge" / "data" / "forge.db").is_file()

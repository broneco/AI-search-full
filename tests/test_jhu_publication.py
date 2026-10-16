"""Actual Git snapshots and guarded sync without network, credentials or cloud writes."""
import hashlib
import io
import json
from pathlib import Path
import shutil
import stat
import subprocess
from zipfile import ZipFile, ZipInfo

import pytest

from scripts.publication.jhu import REMOTE, load_export, read_zip, safe_name, write_export
from scripts.publication.sync import sync

ROOT = Path(__file__).resolve().parents[1]


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def commit(root):
    git(root, "add", "--all")
    git(root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "-qm", "Fixture snapshot")
    return git(root, "rev-parse", "HEAD")


@pytest.fixture
def source(tmp_path):
    source = tmp_path/"source"
    source.mkdir()
    git(source, "init", "-q", "-b", "main")
    names = ["pyproject.toml", "dev.ps1", "deploy_backend.ps1", "deploy_frontend.ps1", "AGENTS.md",
             "app/core/config.py", "app/storage/db.py", "frontend-user/app/config/themes.ts",
             "frontend-admin/app/config/themes.ts", "frontend-user/app/page.tsx", "frontend-admin/app/page.tsx"]
    for name in names:
        target = source/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, target)
    for directory in ("publication", ".agents"):
        shutil.copytree(ROOT/directory, source/directory)
    for name in ("tenants/jhu/branding.json", "tenants/jhu/prompts.json", "tenants/jhu/logo.webp",
                 "tenants/default/search_config.json", "tenants/default/classification_config.json"):
        target = source/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, target)
    # Non-runtime historical and secret-bearing files must never enter the customer snapshot.
    (source/"tenants/jhu/.env.prod").write_text("PASSWORD=synthetic-private-fixture", encoding="utf-8")
    (source/"tenants/other").mkdir()
    (source/"tenants/other/prompts.json").write_text('{"cs":"other-client"}', encoding="utf-8")
    (source/"docs/releases").mkdir(parents=True)
    (source/"docs/releases/internal.md").write_text("private development diary", encoding="utf-8")
    (source/"scripts").mkdir()
    (source/"scripts/internal.txt").write_text("internal operator", encoding="utf-8")
    (source/".env.example").write_text("APP_ENV=dev\n", encoding="utf-8")
    (source/"tests").mkdir()
    (source/"tests/test_sample.py").write_text("def test_sample():\n    assert True\n", encoding="utf-8")
    sha = commit(source)
    return source, sha


@pytest.fixture
def exported(source, tmp_path):
    source, sha = source
    archive = tmp_path/"handoff.zip"
    manifest = write_export(source, sha, archive)
    return archive, manifest


@pytest.fixture
def target(tmp_path):
    target = tmp_path/"target"
    target.mkdir()
    git(target, "init", "-q", "-b", "main")
    git(target, "remote", "add", "origin", REMOTE)
    return target


def test_committed_snapshot_excludes_worktree_history_and_secrets(source, tmp_path):
    source, sha = source
    (source/"uncommitted.txt").write_text("must not ship", encoding="utf-8")
    archive = tmp_path/"handoff.zip"
    manifest = write_export(source, sha, archive)
    payload, _ = load_export(archive)
    assert manifest["source_commit"] == sha
    assert "uncommitted.txt" not in payload
    assert "tenants/jhu/.env.prod" not in payload
    assert "docs/releases/internal.md" not in payload
    assert not any(name.startswith((".git/", "publication/", "scripts/", ".agents/memory/archive/")) for name in payload)
    assert {name.split('/')[1] for name in payload if name.startswith('tenants/')} == {"jhu"}
    assert "tenants/jhu/search_config.json" in payload
    assert b'CLIENT_THEMES.dolphin' not in payload['frontend-user/app/page.tsx']
    assert manifest["version"].encode() in payload["README.md"]
    assert sha.encode() not in b''.join(payload.values())
    assert hashlib.sha256(payload["tenants/jhu/search_config.json"]).hexdigest() == manifest["files"]["tenants/jhu/search_config.json"]


def test_projection_drift_fails_without_writing_output(source, tmp_path):
    source, sha = source
    path = source/"dev.ps1"
    path.write_text(path.read_text(encoding='utf-8').replace("TENANT_ID=dolphin", "TENANT_ID=renamed"), encoding='utf-8')
    sha = commit(source)
    with pytest.raises(ValueError, match="drift"):
        write_export(source, sha, tmp_path/"bad.zip")
    assert not (tmp_path/"bad.zip").exists()


def test_export_does_not_overwrite_existing_handoff(exported, source):
    archive, manifest = exported
    before = archive.read_bytes()
    with pytest.raises(ValueError, match="never overwritten"):
        write_export(source[0], source[1], archive)
    assert archive.read_bytes() == before


def test_sync_plan_apply_and_next_snapshot_keep_git_and_private_files(exported, target):
    archive, manifest = exported
    (target/'.git/info/exclude').write_text('.env.local\n', encoding='utf-8')
    secret = target/'.env.local'
    secret.write_text('PASSWORD=local-fixture-only', encoding='utf-8')
    plan = sync(archive, target)
    assert plan["head"] == "EMPTY" and not plan["apply"]
    assert not (target/"README.md").exists()
    with pytest.raises(ValueError, match="expect-head"):
        sync(archive, target, apply=True, expect_head="wrong")
    sync(archive, target, apply=True, expect_head="EMPTY")
    first = commit(target)
    assert git(target, "rev-list", "--count", "HEAD") == "1"
    (target/"stale.txt").write_text("previous snapshot only", encoding="utf-8")
    previous = commit(target)
    plan = sync(archive, target)
    assert "stale.txt" in plan["remove"] and (target/"stale.txt").exists()
    sync(archive, target, apply=True, expect_head=previous)
    last = commit(target)
    assert git(target, "rev-parse", "HEAD^") == previous
    assert first != last and not (target/"stale.txt").exists()
    assert secret.read_text(encoding="utf-8") == 'PASSWORD=local-fixture-only'
    assert git(target, "remote", "get-url", "origin") == REMOTE


@pytest.mark.parametrize("issue", ["dirty", "origin", "branch"])
def test_sync_rejects_unreviewed_target(exported, target, issue):
    (target/"initial.txt").write_text("initial", encoding="utf-8")
    commit(target)
    if issue == "dirty":
        (target/"initial.txt").write_text("local edit", encoding="utf-8")
    elif issue == "origin":
        git(target, "remote", "set-url", "origin", "https://github.com/example/development.git")
    else:
        git(target, "switch", "-qc", "codex/unreviewed")
    with pytest.raises(ValueError):
        sync(exported[0], target, apply=True, expect_head=git(target, "rev-parse", "HEAD"))
    assert not (target/"README.md").exists()


def test_modified_archive_is_rejected_before_destination_write(exported, target):
    archive, _ = exported
    with ZipFile(archive, "a") as altered:
        altered.writestr("extra.txt", "unreviewed")
    with pytest.raises(ValueError, match="manifest differ"):
        sync(archive, target)
    assert not (target/"README.md").exists()


@pytest.mark.parametrize("path", ["../.git/config", "/absolute", "C:/outside", "app\\file", "app//file"])
def test_archive_path_escape_is_rejected(path):
    with pytest.raises(ValueError, match="Unsafe"):
        safe_name(path)


def test_symbolic_links_are_rejected():
    data = io.BytesIO()
    with ZipFile(data, "w") as archive:
        entry = ZipInfo("escape")
        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(entry, "../outside")
    with pytest.raises(ValueError, match="symbolic"):
        read_zip(data.getvalue())


@pytest.mark.parametrize("path", [".GIT/config", ".ENV.PROD", "tenants/jhu/.Env.dev", "NODE_MODULES/package/index.js"])
def test_windows_case_aliases_cannot_publish_metadata_or_private_files(path):
    assert safe_name(path) is False

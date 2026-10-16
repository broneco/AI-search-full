"""Read-only sync plan; explicit Apply changes only a separate clean checkout."""
import hashlib
from pathlib import Path
import subprocess

from scripts.publication.jhu import REMOTE, git, load_export, safe_name


def sync(archive: Path, destination: Path, *, apply: bool = False, expect_head: str | None = None) -> dict:
    payload, manifest = load_export(archive)
    destination = destination.resolve(strict=True)
    root = Path(git(destination, "rev-parse", "--show-toplevel")).resolve()
    if root != destination or not (destination / ".git").is_dir():
        raise ValueError("Use the root of an independent clone, not a subdirectory or worktree.")
    if git(destination, "remote", "get-url", "origin") != REMOTE:
        raise ValueError("Publication origin mismatch; the development repository must never be a sync target.")
    if git(destination, "symbolic-ref", "--short", "HEAD") != "main":
        raise ValueError("Publication checkout must be on main.")
    if git(destination, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("Publication checkout is dirty; reconcile local changes first.")
    process = subprocess.run(["git", "-C", str(destination), "rev-parse", "--verify", "HEAD"], capture_output=True, text=True)
    head = process.stdout.strip() if process.returncode == 0 else "EMPTY"
    if apply and expect_head != head:
        raise ValueError("Apply requires --expect-head matching the reviewed target commit (or EMPTY).")
    files = subprocess.check_output(["git", "-C", str(destination), "ls-files", "-z"]).decode("utf-8").split("\0")
    tracked = {name for name in files if name}
    for name in tracked | set(payload):
        if not safe_name(name):
            raise ValueError("Tracked private/generated files require manual reconciliation.")
        target = destination / name
        if not target.resolve().is_relative_to(destination):
            raise ValueError("Destination path escapes the checkout.")
        for parent in [target, *target.parents]:
            if parent == destination:
                break
            if parent.is_symlink() or (hasattr(parent, "is_junction") and parent.is_junction()):
                raise ValueError("Destination symlink/junction requires manual review.")
        if target.exists() and (not target.is_file() or name not in tracked):
            raise ValueError("Handoff collides with a directory or untracked local file.")
    changed = sorted(name for name, data in payload.items() if name not in tracked or
                     hashlib.sha256((destination/name).read_bytes()).digest() != hashlib.sha256(data).digest())
    removed = sorted(tracked - set(payload))
    report = {"remote": REMOTE, "head": head, "version": manifest["version"], "apply": apply,
              "write": changed, "remove": removed, "source_commit": manifest["source_commit"]}
    if apply:
        # Recheck immediately before writes. No Git refs/index or network are changed.
        if git(destination, "status", "--porcelain", "--untracked-files=all"):
            raise ValueError("Checkout changed after planning.")
        current = subprocess.run(["git", "-C", str(destination), "rev-parse", "--verify", "HEAD"], capture_output=True, text=True)
        if (current.stdout.strip() if current.returncode == 0 else "EMPTY") != head:
            raise ValueError("Target HEAD changed after planning.")
        for name in removed:
            (destination/name).unlink()
        for name in changed:
            target = destination/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload[name])
    return report

"""Build the JHU handoff from a committed Git ref, without copying Git history."""
import ast
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import stat
import subprocess
import tomllib
from urllib.parse import unquote, urlsplit
from zipfile import ZipFile, ZIP_DEFLATED

REMOTE = "https://forgejo.jcu.cz/dconsulting/jhu-ai-search.git"
TEMPLATES = "publication/jhu/templates/"
INTERNAL = ("scripts/", "publication/", ".agents/memory/", ".agents/inbox/", ".github/")
INTERNAL_FILES = {"export_jhu.py", "prepare_jhu_publication.py", "probe_jhu_vpn.py", "tests/test_vpn_spike.py", "tests/test_jhu_helper.py", "tests/test_jhu_publication.py", ".agents/workflows/jhu-publication.md"}
FORBIDDEN = {".git", ".local", ".venv", "node_modules", ".next", "out", "__pycache__", "data", "data - full backup", "data-full backup", "scratch"}


def is_adr(name: str) -> bool:
    """The JHU publication omits ADR documents, not the rest of the public manuals/history."""
    path = PurePosixPath(name)
    return "adr" in {part.casefold() for part in path.parts} or path.name.casefold().startswith("adr-")


def documentation_links(payload: dict[str, bytes], original: dict[str, bytes], version: str) -> None:
    """Keep prose; unlink omitted ADRs and link omitted development-only sources upstream."""
    directories = {str(parent) for name in original for parent in PurePosixPath(name).parents}
    for name, data in list(payload.items()):
        if not name.endswith(".md"):
            continue
        def rewrite(match):
            label, reference = match.group(1), match.group(2)
            url = urlsplit(reference.strip("<>"))
            if url.scheme or not url.path or "<" in reference:
                return match.group(0)
            target = posixpath.normpath(posixpath.join(posixpath.dirname(name), unquote(url.path)))
            if is_adr(target):
                return label
            if target in payload or any(item.startswith(target.rstrip("/") + "/") for item in payload):
                return match.group(0)
            if target in original or target in directories:
                suffix = ("#" + url.fragment) if url.fragment else ""
                kind = "blob" if target in original else "tree"
                return f"[{label}](https://github.com/broneco/AI-search-full/{kind}/{version}/{target}{suffix})"
            return match.group(0)  # Unknown broken links still fail validation.
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", rewrite, data.decode("utf-8-sig"))
        payload[name] = text.encode("utf-8")


def git(root: Path, *args: str) -> str:
    process = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    if process.returncode:
        raise ValueError("Git operation failed: " + " ".join(args[:2]))
    return process.stdout.strip()


def safe_name(name: str) -> bool:
    """Reject unsafe paths; identify private/generated files without logging content."""
    path = PurePosixPath(name)
    if (not name or name == "." or str(path) != name or "\\" in name or ":" in name
            or path.is_absolute() or ".." in path.parts
            or any(part.rstrip(" .") != part for part in path.parts)):
        raise ValueError("Unsafe archive path.")
    return (not ({part.casefold() for part in path.parts} & FORBIDDEN)
            and (not path.name.casefold().startswith(".env") or name == ".env.example")
            and not path.name.casefold().endswith(".manifest.json")
            and path.suffix.lower() not in {".pem", ".key", ".pfx", ".ovpn", ".auth", ".pyc", ".log", ".zip"})


def read_zip(data: bytes) -> dict[str, bytes]:
    result = {}
    seen = set()
    with ZipFile(io.BytesIO(data)) as archive:
        for item in archive.infolist():
            if item.is_dir():
                continue
            if item.filename.casefold() in seen or stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError("Duplicate paths or symbolic links are not allowed.")
            seen.add(item.filename.casefold())
            if safe_name(item.filename):
                result[item.filename] = archive.read(item)
    return result


def source_snapshot(root: Path, ref: str) -> tuple[dict[str, bytes], str]:
    sha = git(root, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}")
    process = subprocess.run(["git", "-C", str(root), "archive", "--format=zip", sha], capture_output=True)
    if process.returncode:
        raise ValueError("Unable to archive the selected committed ref.")
    return read_zip(process.stdout), sha


def validate(payload: dict[str, bytes]) -> None:
    if {name.split("/")[1] for name in payload if name.startswith("tenants/")} != {"jhu"}:
        raise ValueError("The handoff must contain only tenants/jhu.")
    if any(not safe_name(name) for name in payload):
        raise ValueError("Private/generated content in handoff.")
    for name, data in payload.items():
        if name.startswith(".agents/memory/archive/") or is_adr(name):
            raise ValueError("Private agent history and ADR files are not part of the handoff.")
        if not name.endswith(".md"):
            continue
        for link in re.findall(r"\]\(([^)]+)\)", data.decode("utf-8-sig")):
            url = urlsplit(link.strip("<>"))
            if url.scheme or not url.path or "<" in link:
                continue
            target = posixpath.normpath(posixpath.join(posixpath.dirname(name), unquote(url.path)))
            if target not in payload and not any(item.startswith(target.rstrip("/") + "/") for item in payload):
                raise ValueError(f"Unresolved documentation link in {name}: {link}")


def project(original: dict[str, bytes]) -> tuple[dict[str, bytes], str]:
    """Explicit JHU variants; template/code drift fails before any destination write."""
    version = "v" + tomllib.loads(original["pyproject.toml"].decode("utf-8-sig"))["project"]["version"]
    payload = {name: data for name, data in original.items()
               if (not name.startswith(INTERNAL) or name.startswith(('scripts/vpn_spike/', 'scripts/deployment/'))) and name not in INTERNAL_FILES
               and not is_adr(name)
               and (not name.startswith("tenants/") or name.startswith("tenants/jhu/"))
               and ("/public/logos/" not in name or name.endswith("/logo-JHU.webp"))}
    for filename in ("search_config.json", "classification_config.json", "model_config.json", "embedding_config.json", "local_model_recipes.json"):
        name = "tenants/jhu/" + filename
        if name not in payload:
            payload[name] = original["tenants/default/" + filename]

    def replace(name: str, old: str, new: str) -> None:
        text = payload[name].decode("utf-8-sig")
        if old not in text:
            raise ValueError(f"JHU projection requires review after source drift: {name}")
        payload[name] = text.replace(old, new).encode("utf-8")

    theme = json.loads(payload["tenants/jhu/branding.json"])
    for app in ("frontend-user", "frontend-admin"):
        name = app + "/app/config/themes.ts"
        text = payload[name].decode("utf-8-sig")
        if "export const CLIENT_THEMES:" not in text:
            raise ValueError("Frontend theme interface changed; review the projection.")
        interface = text.split("export const CLIENT_THEMES:", 1)[0]
        payload[name] = (interface + "export const CLIENT_THEMES: Record<string, ClientTheme> = "
                         + json.dumps({"jhu": theme}, ensure_ascii=False, indent=2)
                         + ';\n\nexport const DEFAULT_THEME_ID = "jhu";\n').encode("utf-8")
        replace(app + "/app/page.tsx", 'useState<string>("dolphin")', "useState<string>(DEFAULT_THEME_ID)")
        replace(app + "/app/page.tsx", "CLIENT_THEMES.dolphin", "CLIENT_THEMES[DEFAULT_THEME_ID]")
    replace("dev.ps1", "TENANT_ID=dolphin", "TENANT_ID=jhu")
    replace("app/core/config.py", 'TENANT_ID: str = "dolphin"', 'TENANT_ID: str = "jhu"')
    for name in ("deploy_backend.ps1", "deploy_frontend.ps1"):
        text = payload[name].decode("utf-8-sig")
        pattern = r"(\$Client\s*=\s*['\"])showcase(['\"])"
        if not re.search(pattern, text):
            raise ValueError(f"Deployment default changed; review projection: {name}")
        payload[name] = re.sub(pattern, r"\g<1>jhu\2", text).encode("utf-8")
    for old, new in (("user@dolphin.cz", "user@jcu.cz"), ("admin@dolphin.cz", "admin@jcu.cz"),
                     ("user@dolphinconsulting.cz", "user.demo@jcu.cz"),
                     ("Dolphin Demo Uživatel", "JCU Demo Uživatel"), ("Dolphin Admin", "JCU Admin")):
        replace("app/storage/db.py", old, new)

    templates = {name.removeprefix(TEMPLATES): data for name, data in original.items() if name.startswith(TEMPLATES)}
    if "README.md" not in templates or ".agents/AGENTS.md" not in templates:
        raise ValueError("Committed JHU documentation templates are missing.")
    for name, data in templates.items():
        if not is_adr(name) and (name not in payload or (not name.startswith("docs/") and name != "README.md")):
            payload[name] = data.decode("utf-8-sig").replace("@@VERSION@@", version).encode("utf-8")
    # Preserve the complete source README, with a small explicit note about the JHU-only runtime.
    readme = payload["README.md"].decode("utf-8-sig")
    notice = (f"> Předání JHU {version}: konfigurace a branding tohoto balíčku obsahují pouze JHU. "
              "Níže je úplná veřejná dokumentace hlavního projektu; příklady jiných tenantů jsou obecný kontext. "
              "ADR soubory jsou vynechané. Pro existující cloud se sidecarem použijte "
              "[JHU cloudový postup](docs/development/jhu-sidecar-azure.md).\n\n")
    payload["README.md"] = (notice + readme).encode("utf-8")
    for name, data in list(payload.items()):
        if name.startswith("tests/test_") and name.endswith(".py"):
            tree = ast.parse(data.decode("utf-8-sig"))
            functions = [node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                         and node.name.startswith("test_")]
            doc = "docs/tests_explained/" + PurePosixPath(name).stem + ".md"
            if doc in payload:
                continue  # Existing detailed explanations are documentation, not generated placeholders.
            payload[doc] = ("# " + PurePosixPath(name).stem + "\n\nAktuální testy v [" + name + "](../../" + name
                            + "). [Postup testování](../development/testing.md).\n\n"
                            + "\n".join("- `" + item + "`" for item in functions) + "\n").encode("utf-8")
    payload["docs/navigation_guide.md"] = b""
    lines = ["# Mapa aktuálního repozitáře", "", "Pouze předané zdroje a současná dokumentace.", ""]
    descriptions = dict(re.findall(r"^- `([^`]+)` — (.+)$", original.get("docs/navigation_guide.md", b"").decode("utf-8-sig"), re.MULTILINE))
    for name in sorted(payload):
        label = descriptions.get(name) or ((payload[name].decode("utf-8-sig").splitlines() or ["Mapa aktuálního repozitáře"])[0].lstrip("# ") if name.endswith(".md") else "Součást aktuální implementace projektu.")
        lines.append("- `" + name + "` — " + label)
    payload["docs/navigation_guide.md"] = ("\n".join(lines) + "\n").encode("utf-8")
    documentation_links(payload, original, version)
    validate(payload)
    return payload, version


def write_export(root: Path, ref: str, output: Path) -> dict:
    original, sha = source_snapshot(root, ref)
    payload, version = project(original)
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in sorted(payload.items())}
    # Internal provenance is a sidecar, not part of the customer archive/history.
    manifest = {"schema": 1, "version": version, "source_commit": sha, "remote": REMOTE, "files": hashes}
    output = output.resolve()
    if output.suffix.lower() != ".zip":
        raise ValueError("Output must be a .zip file.")
    if output.exists() or output.with_suffix(".manifest.json").exists():
        raise ValueError("Choose a new output path; existing handoffs are never overwritten.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "x", ZIP_DEFLATED) as archive:
        for name, data in sorted(payload.items()):
            archive.writestr(name, data)
    output.with_suffix(".manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def load_export(path: Path) -> tuple[dict[str, bytes], dict]:
    manifest = json.loads(path.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != 1 or manifest.get("remote") != REMOTE:
        raise ValueError("Invalid publication manifest.")
    payload = read_zip(path.read_bytes())
    with ZipFile(path) as archive:
        if set(archive.namelist()) != set(payload):
            raise ValueError("Handoff contains private/generated entries.")
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in payload.items()}
    if hashes != manifest.get("files"):
        raise ValueError("Archive and manifest differ; regenerate and review the handoff.")
    validate(payload)
    return payload, manifest

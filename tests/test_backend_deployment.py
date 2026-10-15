"""Run the release script with a fake native Azure CLI; never contact Azure."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHELLS = [p for name in ("powershell.exe", "pwsh.exe") if (p := shutil.which(name))]
pytestmark = pytest.mark.skipif(os.name != "nt" or not SHELLS, reason="Windows PowerShell deployment checks")
SECRET_MARKER = "private-value-must-never-appear"
IMAGE = "registry.azurecr.io/backend:previous"


def fixture_app():
    values = {
        "APP_ENV": "prod", "TENANT_ID": "ju-prod", "AZURE_SQL_HOST": "sql.example",
        "AZURE_SQL_DB": "database", "AZURE_SQL_USER": "app-user", "AZURE_SQL_DRIVER": "driver",
        "AZURE_BLOB_CONTAINER_ORIGINALS": "originals", "AZURE_OPENAI_ENDPOINT": "https://model.example",
        "AZURE_OPENAI_FLASH_DEPLOYMENT": "mini", "AZURE_OPENAI_THINKING_DEPLOYMENT": "mini",
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": "embedding", "AZURE_OPENAI_EMBEDDING_MODEL": "model",
        "AZURE_OPENAI_EMBEDDING_MODEL_REVISION": "1", "AZURE_OPENAI_EMBEDDING_DIMENSIONS": "1536",
        "EMBEDDING_PROVIDER": "azure_openai", "LLM_PROVIDER": "azure_openai",
        "AZURE_OPENAI_EMBEDDING_QUERY_PREFIX": "", "AZURE_OPENAI_EMBEDDING_DOCUMENT_PREFIX": "",
        "AZURE_SQL_PASSWORD": SECRET_MARKER, "AZURE_OPENAI_API_KEY": SECRET_MARKER,
        "AZURE_STORAGE_CONNECTION_STRING": SECRET_MARKER,
    }
    return {"properties": {"latestReadyRevisionName": "previous-revision", "configuration": {
        "secrets": [{"name": "jwt"}], "ingress": {"targetPort": 8000}}, "template": {
        "scale": {"minReplicas": 1, "maxReplicas": 3}, "containers": [{
            "name": "simple-hello-world-container", "image": IMAGE,
            "env": [{"name": k, "value": v} for k, v in values.items()] + [
                {"name": "JWT_SECRET", "secretRef": "jwt"}],
            "resources": {"cpu": .5, "memory": "1Gi"}}]}}}


def run_release(tmp_path, shell, *, args=(), mutate=None, fail="", concurrent=False):
    shutil.copyfile(ROOT / "deploy_backend.ps1", tmp_path / "deploy_backend.ps1")
    folder = tmp_path / "tenants" / "jhu"
    folder.mkdir(parents=True)
    (folder / ".env.prod").write_text(
        "APP_ENV=prod\nTENANT_ID=ju-prod\nAZURE_RESOURCE_GROUP=group\n"
        "AZURE_CONTAINER_APP_NAME=backend\nAZURE_CONTAINER_REGISTRY=registry\n"
        f"AZURE_SQL_HOST=sql.example\nAZURE_SQL_DB=database\nJWT_SECRET={SECRET_MARKER}\n",
        encoding="utf-8")
    app = fixture_app()
    if mutate:
        mutate(app)
    (tmp_path / "app.json").write_text(json.dumps(app), encoding="utf-8")
    (tmp_path / "az.cmd").write_text(
        f'@echo off\n"{sys.executable}" "{tmp_path / "fake_az.py"}" %*\nexit /b %errorlevel%\n',
        encoding="ascii")
    (tmp_path / "fake_az.py").write_text('''
import json, os, pathlib, sys
root=pathlib.Path(__file__).parent
args=sys.argv[1:]
with (root / "calls.jsonl").open("a") as f: f.write(json.dumps(args)+"\\n")
key=" ".join(args[:2])
if key == os.environ.get("FAKE_AZ_FAIL"):
    print("private-value-must-never-appear")
    raise SystemExit(9)
if key == "account show": result={"id":"subscription", "tenantId":"azure-tenant"}
elif key == "acr show": result={"loginServer":"registry.azurecr.io"}
elif key == "containerapp show":
    result=json.loads((root / "app.json").read_text())
    if os.environ.get("FAKE_CONCURRENT") and (root / "built").exists():
        result["properties"]["template"]["scale"]["maxReplicas"]=4
elif key == "acr build":
    (root / "built").touch()
    result={"status":"Succeeded"}
elif key == "containerapp update": result={"status":"Succeeded"}
else: raise SystemExit(90)
print("WARNING: harmless CLI warning", file=sys.stderr)
print(json.dumps(result))
''', encoding="utf-8")
    env = os.environ.copy()
    env["PATH"] = str(tmp_path) + os.pathsep + env.get("PATH", "")
    env["FAKE_AZ_FAIL"] = fail
    env["FAKE_CONCURRENT"] = "1" if concurrent else ""
    result = subprocess.run([shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
        str(tmp_path / "deploy_backend.ps1"), "-Client", "ju", "-Environment", "prod", *args],
        cwd=tmp_path, env=env, capture_output=True, text=True, errors="replace", timeout=40)
    calls_path = tmp_path / "calls.jsonl"
    calls = [json.loads(line) for line in calls_path.read_text().splitlines()] if calls_path.exists() else []
    assert SECRET_MARKER not in result.stdout + result.stderr
    return result, calls


APPLY = ("-Apply", "-ExpectedSubscriptionId", "subscription", "-ExpectedAzureTenantId", "azure-tenant",
         "-ExpectedCurrentImage", IMAGE, "-MigrationConfirmed", "-JwtMigrationConfirmed")


@pytest.mark.parametrize("shell", SHELLS or [None])
def test_default_plan_is_read_only_and_preserves_tenant(tmp_path, shell):
    result, calls = run_release(tmp_path, shell)
    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    assert plan["tenant"] == "ju-prod"
    assert plan["blockers"] == []
    assert [c[:2] for c in calls] == [["account", "show"], ["containerapp", "show"], ["acr", "show"]]
    assert all(c[c.index("--subscription") + 1] == "subscription" for c in calls[1:])


@pytest.mark.parametrize("shell", SHELLS or [None])
@pytest.mark.parametrize("default_present", [False, True])
def test_existing_keyvault_can_supply_jwt_without_new_secret_refs(tmp_path, shell, default_present):
    def mutate(app):
        items = app["properties"]["template"]["containers"][0]["env"]
        items[:] = [item for item in items if item["name"] != "JWT_SECRET"]
        items.extend([{"name": "AZURE_KEY_VAULT_NAME", "value": "existing-vault"},
            {"name": "AZURE_KEY_VAULT_SECRET_JWT_SIGNING_KEY", "value": "new-jwt"}])
        if default_present:
            items.append({"name": "JWT_SECRET", "value": "dolphin-ai-search-secret-key-2026"})
    result, calls = run_release(tmp_path, shell, mutate=mutate)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["blockers"] == []
    assert all(c[:2] in [["account", "show"], ["containerapp", "show"], ["acr", "show"]] for c in calls)


@pytest.mark.parametrize("shell", SHELLS or [None])
@pytest.mark.parametrize("scenario", ["wrong-subscription", "wrong-tenant", "missing-confirmation", "wrong-image",
                                     "runtime-tenant", "default-jwt", "missing-jwt", "missing-profile",
                                     "broken-secret-ref", "cli-failure"])
def test_invalid_release_stops_before_any_write(tmp_path, shell, scenario):
    args = list(APPLY)
    mutate = None
    fail = ""
    if scenario == "wrong-subscription": args[args.index("subscription")] = "other"
    if scenario == "wrong-tenant": args[args.index("azure-tenant")] = "other"
    if scenario == "missing-confirmation": args.remove("-JwtMigrationConfirmed")
    if scenario == "wrong-image": args[args.index(IMAGE)] = IMAGE + "-changed"
    if scenario == "runtime-tenant":
        def mutate(app):
            next(e for e in app["properties"]["template"]["containers"][0]["env"] if e["name"] == "TENANT_ID")["value"] = "jhu-prod"
    if scenario in {"default-jwt", "missing-jwt"}:
        def mutate(app):
            items = app["properties"]["template"]["containers"][0]["env"]
            items[:] = [e for e in items if e["name"] != "JWT_SECRET"]
            if scenario == "default-jwt":
                items.append({"name": "JWT_SECRET", "value": "dolphin-ai-search-secret-key-2026"})
    if scenario == "missing-profile":
        def mutate(app):
            items = app["properties"]["template"]["containers"][0]["env"]
            items[:] = [e for e in items if e["name"] != "AZURE_OPENAI_EMBEDDING_MODEL_REVISION"]
    if scenario == "broken-secret-ref":
        def mutate(app):
            app["properties"]["configuration"]["secrets"] = []
    if scenario == "cli-failure": fail = "containerapp show"
    result, calls = run_release(tmp_path, shell, args=args, mutate=mutate, fail=fail)
    assert result.returncode != 0
    assert all(c[:2] in [["account", "show"], ["containerapp", "show"], ["acr", "show"]] for c in calls)


@pytest.mark.parametrize("shell", SHELLS or [None])
def test_approved_release_only_builds_and_updates_image(tmp_path, shell):
    result, calls = run_release(tmp_path, shell, args=APPLY)
    assert result.returncode == 0, result.stderr
    assert [c[:2] for c in calls] == [["account", "show"], ["containerapp", "show"], ["acr", "show"],
        ["acr", "build"], ["containerapp", "show"], ["containerapp", "update"]]
    update = calls[-1]
    assert update[update.index("--container-name") + 1] == "simple-hello-world-container"
    assert "--set-env-vars" not in update
    assert "--min-replicas" not in update
    assert all(":latest" not in arg for c in calls for arg in c)


@pytest.mark.parametrize("shell", SHELLS or [None])
def test_concurrent_change_after_build_prevents_update(tmp_path, shell):
    result, calls = run_release(tmp_path, shell, args=APPLY, concurrent=True)
    assert result.returncode != 0
    assert ["acr", "build"] in [c[:2] for c in calls]
    assert ["containerapp", "update"] not in [c[:2] for c in calls]


@pytest.mark.parametrize("shell", SHELLS or [None])
def test_failed_build_does_not_update_app_or_print_credentials(tmp_path, shell):
    result, calls = run_release(tmp_path, shell, args=APPLY, fail="acr build")
    assert result.returncode != 0
    assert calls[-1][:2] == ["acr", "build"]


@pytest.mark.parametrize("shell", SHELLS or [None])
def test_legacy_combined_deploy_cannot_write(tmp_path, shell):
    # No mock az is needed: the wrapper must terminate before invoking any tool.
    result = subprocess.run([shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
        str(ROOT / "deploy_all.ps1")], cwd=tmp_path, capture_output=True, timeout=15)
    assert result.returncode != 0
    assert b"Combined deployment is disabled" in result.stderr

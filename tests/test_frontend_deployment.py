"""Execute deployment with native fake commands; no Azure/npm/network calls."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHELLS = [p for name in ("powershell.exe", "pwsh.exe") if (p := shutil.which(name))]
pytestmark = pytest.mark.skipif(os.name != "nt" or not SHELLS, reason="Windows release checks")
TOKEN = "synthetic-private-deployment-token"


def run_frontend(tmp_path, shell, *, apply=False, fail="", extra=()):
    shutil.copyfile(ROOT / "deploy_frontend.ps1", tmp_path / "deploy_frontend.ps1")
    folder = tmp_path / "frontend-user"
    (folder / "out").mkdir(parents=True)
    (folder / "package.json").write_text("{}", encoding="utf-8")
    (folder / "out/index.html").write_text("fixture", encoding="utf-8")
    binary = tmp_path / "bin"
    binary.mkdir()
    helper = binary / "fake.py"
    helper.write_text('''import json,os,sys
from pathlib import Path
args=sys.argv[1:]
with open(os.environ["CALLS"],"a") as f:f.write(json.dumps(args)+"\\n")
command=args[0]; args=args[1:]
if command=="npx":
    if os.environ.get("SWA_CLI_DEPLOYMENT_TOKEN")!="synthetic-private-deployment-token":sys.exit(8)
    if os.environ.get("SWA_CLI_DEBUG")!="error":sys.exit(8)
    if "--deployment-token" in args:sys.exit(8)
if os.environ.get("FAIL")==command or os.environ.get("FAIL")=="token" and args[:3]==["staticwebapp","secrets","list"]:sys.exit(7)
if command!="az":sys.exit(0)
if args[:2]==["account","show"]:result={"id":"subscription","tenantId":"directory"}
elif args[:2]==["staticwebapp","show"]:result={"id":"swa-id","defaultHostname":"fixture.azurestaticapps.net"}
elif args[:3]==["staticwebapp","secrets","list"]:result={"properties":{"apiKey":"synthetic-private-deployment-token"}}
else:sys.exit(9)
print(json.dumps(result))
''', encoding="utf-8")
    for name in ("az", "npm", "npx"):
        (binary / (name+".cmd")).write_text(f'@echo off\n"{sys.executable}" "{helper}" {name} %*\nexit /b %errorlevel%\n', encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("AZURE_")}
    env.update(PATH=str(binary)+os.pathsep+env["PATH"], CALLS=str(tmp_path/"calls"), FAIL=fail)
    args = [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(tmp_path/"deploy_frontend.ps1"),
            "-Client", "ju", "-Environment", "prod", "-ResourceGroup", "group", "-StaticWebAppName", "swa",
            "-BackendUrl", "https://backend.example.test"]
    if apply:
        args += ["-Apply", "-ExpectedSubscriptionId", "subscription", "-ExpectedAzureTenantId", "directory"]
    result = subprocess.run(args+list(extra), cwd=tmp_path, env=env, capture_output=True, text=True, errors="replace", timeout=45)
    calls = [json.loads(line) for line in (tmp_path/"calls").read_text().splitlines()] if (tmp_path/"calls").exists() else []
    assert TOKEN not in result.stdout+result.stderr
    return result, calls


@pytest.mark.parametrize("shell", SHELLS)
def test_frontend_plan_is_read_only(tmp_path, shell):
    result, calls = run_frontend(tmp_path, shell)
    assert result.returncode == 0, result.stderr
    assert all(call[0] == "az" and call[1:3] in [["account", "show"], ["staticwebapp", "show"]] for call in calls)


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("failure", ["az", "npm", "token", "npx"])
def test_frontend_errors_stop_without_provisioning(tmp_path, shell, failure):
    result, calls = run_frontend(tmp_path, shell, apply=True, fail=failure)
    assert result.returncode != 0
    assert not any("create" in call for call in calls)
    if failure != "npx":
        assert not any(call[0] == "npx" for call in calls)


@pytest.mark.parametrize("shell", SHELLS)
def test_frontend_apply_targets_only_existing_app(tmp_path, shell):
    result, calls = run_frontend(tmp_path, shell, apply=True)
    assert result.returncode == 0, result.stderr
    assert any(call[0] == "npx" for call in calls)
    assert not any("create" in call for call in calls)
    assert all(TOKEN not in json.dumps(call) and '--deployment-token' not in call for call in calls)


@pytest.mark.parametrize("shell", SHELLS)
def test_frontend_rejects_wrong_subscription(tmp_path, shell):
    result, calls = run_frontend(tmp_path, shell, extra=["-ExpectedSubscriptionId", "different"])
    assert result.returncode != 0
    assert not any(call[0] in {"npm", "npx"} for call in calls)

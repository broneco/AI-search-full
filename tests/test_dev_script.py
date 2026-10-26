"""Exercise native stderr and exit codes through the real development script."""

import os
from pathlib import Path
import shutil
import subprocess
import json
import sys

import pytest


POWERSHELLS = [
    executable
    for name in ("powershell.exe", "pwsh.exe")
    if (executable := shutil.which(name))
]
pytestmark = pytest.mark.skipif(
    os.name != "nt" or not POWERSHELLS,
    reason="Native Windows PowerShell regression tests",
)


@pytest.mark.parametrize("powershell", POWERSHELLS or [None])
@pytest.mark.parametrize(
    "action,info_exit,compose_exit,expected_success,expected_calls",
    [
        ("stop-db", 0, 0, True, ["compose"]),
        ("stop-db", 0, 13, False, ["compose"]),
        # Successful daemon probe with stderr warning must reach compose.
        # Compose fails deliberately so the test does not wait on a TCP port.
        ("start-db", 0, 13, False, ["info", "compose"]),
        ("start-db", 7, 0, False, ["info"]),
    ],
)
def test_docker_warnings_do_not_replace_native_exit_codes(
    tmp_path, powershell, action, info_exit, compose_exit,
    expected_success, expected_calls,
):
    source = Path(__file__).resolve().parents[1] / "dev.ps1"
    shutil.copyfile(source, tmp_path / "dev.ps1")
    (tmp_path / ".env.local").write_text(
        "APP_ENV=local\nDATABASE_BACKEND=sqlserver\n"
        "AZURE_SQL_HOST=127.0.0.1\nAZURE_SQL_DB=ai_search_local\n"
        "LOCAL_SQL_SA_PASSWORD=unit-test-only\n"
        "AZURE_SQL_PASSWORD=unit-test-only\n",
        encoding="utf-8",
    )
    # A real native process emits stderr, just like docker.exe on Windows.
    # No real daemon, containers, database or credentials are used.
    (tmp_path / "docker.cmd").write_text(
        "@echo off\n"
        'echo %1>> "%DEV_DOCKER_CALLS%"\n'
        "echo WARNING: daemon is not using the default seccomp profile 1>&2\n"
        f'if "%1"=="info" exit /b {info_exit}\n'
        f'if "%1"=="compose" exit /b {compose_exit}\n'
        "exit /b 99\n",
        encoding="ascii",
    )
    calls = tmp_path / "docker-calls.txt"
    env = os.environ.copy()
    env["PATH"] = str(tmp_path) + os.pathsep + env.get("PATH", "")
    env["DEV_DOCKER_CALLS"] = str(calls)
    result = subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         str(tmp_path / "dev.ps1"), "-Action", action],
        cwd=tmp_path, env=env, capture_output=True, timeout=20,
    )

    assert (result.returncode == 0) is expected_success
    assert calls.read_text().splitlines() == expected_calls
    if "compose" in expected_calls:
        assert b"WARNING: daemon" in result.stdout + result.stderr


@pytest.mark.parametrize('powershell', POWERSHELLS or [None])
@pytest.mark.parametrize('tenant,helper_exit', [('jhu', 0), ('ju-prod', 7), ('dolphin', 0)])
def test_managed_backend_startup_is_explicit_and_jhu_failure_preserves_backend(tmp_path, powershell, tenant, helper_exit):
    root = Path(__file__).resolve().parents[1]
    script = (root/'dev.ps1').read_text(encoding='utf-8-sig').replace(
        '$PythonPath = Join-Path $ProjectRoot ".venv\\Scripts\\python.exe"',
        "$PythonPath = '" + sys.executable.replace("'", "''") + "'")
    (tmp_path/'dev.ps1').write_text(script, encoding='utf-8-sig')
    (tmp_path/'.env.local').write_text('APP_ENV=local\nTENANT_ID=dolphin\nDATABASE_BACKEND=sqlserver\n'
        'AZURE_SQL_HOST=127.0.0.1\nAZURE_SQL_DB=ai_search_local\n'
        'LOCAL_SQL_SA_PASSWORD=fake\nAZURE_SQL_PASSWORD=fake\n', encoding='utf-8')
    (tmp_path/'jhu_connection.py').write_text(
        "import json,sys\nfrom pathlib import Path\n"
        "Path('helper.json').write_text(json.dumps(sys.argv[1:]))\n"
        f"raise SystemExit({helper_exit})\n", encoding='utf-8')
    (tmp_path/'uvicorn.py').write_text(
        "import os,json,sys\nfrom pathlib import Path\n"
        "Path('backend-args.json').write_text(json.dumps(sys.argv[1:]))\n"
        "Path('backend.json').write_text(json.dumps({key:value for key,value in os.environ.items() "
        "if key.startswith('JHU_') or key in ('APP_ENV','TENANT_ID')}))\n", encoding='utf-8')
    env = {key:value for key,value in os.environ.items() if not key.startswith('JHU_')}
    result = subprocess.run([powershell, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
        str(tmp_path/'dev.ps1'), '-Action', 'backend', '-Tenant', tenant, '-JhuManaged'],
        cwd=tmp_path, env=env, capture_output=True, timeout=30)
    if tenant == 'dolphin':
        assert result.returncode != 0
        assert not (tmp_path/'helper.json').exists() and not (tmp_path/'backend.json').exists()
        return
    assert result.returncode == 0, result.stdout + result.stderr
    args = json.loads((tmp_path/'helper.json').read_text())
    assert args[:3] == ['start','--tenant',tenant] and '--wait' in args
    config = json.loads((tmp_path/'backend.json').read_text())
    assert config['APP_ENV'] == 'local' and config['TENANT_ID'] == tenant
    assert config['JHU_CONNECTION_MODE'] == 'managed'
    assert config['JHU_HELPER_WORKSPACE'] == str(tmp_path)
    assert config['JHU_API_PASSWORD_SECRET'] == 'ju-ai-search-jhu-api-password-prod'
    assert 'JHU_LLM_PASSWORD' not in config
    backend_args = json.loads((tmp_path/'backend-args.json').read_text())
    assert backend_args[backend_args.index('--reload-dir')+1] == str(tmp_path/'app')
    assert backend_args.count('--reload-dir') == 1
    if helper_exit:
        assert b'JHU helper' in result.stdout + result.stderr

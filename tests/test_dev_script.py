"""Exercise native stderr and exit codes through the real development script."""

import os
from pathlib import Path
import shutil
import subprocess

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

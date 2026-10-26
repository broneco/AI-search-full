"""Opt-in build/import proof against an installed wheel outside the checkout."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(os.getenv("RUN_PACKAGE_TESTS") != "1", reason="Set RUN_PACKAGE_TESTS=1 for the actual wheel build")
def test_wheel_contains_runtime_and_public_resources(tmp_path):
    assert importlib.util.find_spec("setuptools"), "Install setuptools and wheel for the packaging check."
    # Only public sources enter the staging build; poison env file must never enter the wheel.
    import shutil
    stage = tmp_path/"source"
    stage.mkdir()
    for name in ("app", "tenants", "fixtures"):
        shutil.copytree(ROOT/name, stage/name, ignore=shutil.ignore_patterns(".env*", "__pycache__", "*.pyc"))
    for name in ("pyproject.toml", "README.md"):
        shutil.copyfile(ROOT/name, stage/name)
    (stage/"tenants/jhu/.env.prod").write_text("SECRET=synthetic-do-not-package", encoding="utf-8")
    for name in ('Client.ovpn', 'vpn.auth'):
        (stage/'tenants/jhu'/name).write_text('synthetic-private-vpn-fixture', encoding='utf-8')
    subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "--disable-pip-version-check",
                    "--wheel-dir", str(tmp_path/"wheels"), str(stage)], check=True, capture_output=True, text=True)
    installed = tmp_path/"installed"
    with ZipFile(next((tmp_path/"wheels").glob("*.whl"))) as wheel:
        names = wheel.namelist()
        for required in ("app/core/config.py", "app/storage/vector_store.py", "app/api/routes/chat.py",
                         "app/providers/jhu_managed.py", "app/providers/jhu_secrets.py",
                         "app/api/routes/jhu_connection.py",
                         "tenants/jhu/prompts.json", "fixtures/local-university/studijni-rad.pdf"):
            assert required in names
        for resource in (stage/"tenants").rglob("*.json"):
            assert resource.relative_to(stage).as_posix() in names
        assert not any(".env" in name or "__pycache__" in name for name in names)
        assert not any(name.endswith(('.ovpn', '.auth')) for name in names)
        wheel.extractall(installed)
    env = {k:v for k,v in os.environ.items() if not k.startswith(("AZURE_", "POSTGRES_", "RUN_", "JHU_"))
           and k not in {"TENANT_ID", "JWT_SECRET", "LEGACY_PASSWORD_SECRET", "PYTHONPATH", "DATABASE_BACKEND"}}
    env["APP_ENV"] = "test"
    code = """import sys
sys.path.insert(0,sys.argv[1])
import app.main
import app.providers.jhu_managed
from app.core.prompts import get_tenant_prompts_map
from app.ingestion.local_demo import FIXTURE_ROOT
from app.core.embedding_config import embedding_entry
assert get_tenant_prompts_map('ju-prod') == get_tenant_prompts_map('jhu')
assert 'univerzity' in get_tenant_prompts_map('ju-prod')['cs']
assert FIXTURE_ROOT.is_dir()
assert embedding_entry('ju-prod', 'jhu-nomic').space().dimensions == 768
print('wheel-import-ok')
"""
    result = subprocess.run([sys.executable, "-I", "-c", code, str(installed)], cwd=tmp_path,
                            env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "wheel-import-ok" in result.stdout

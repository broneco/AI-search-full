import os
from fastapi.testclient import TestClient
from app.main import app
from app.core.tenant_config import resolve_tenant_file_path

client = TestClient(app)


def test_get_prompts_endpoint():
    response = client.get("/api/prompts")
    assert response.status_code == 200
    data = response.json()
    assert "tenant_id" in data
    assert "prompts" in data
    assert "cs" in data["prompts"]
    assert "en" in data["prompts"]


def test_update_prompt_endpoint():
    test_prompt = "Testovací systémový prompt pro klienta [1]."
    payload = {"locale": "cs", "prompt_text": test_prompt}
    
    from app.core.tenant_config import load_tenant_json, save_tenant_json
    orig = load_tenant_json("default", "prompts.json")
    
    try:
        put_response = client.put("/api/prompts", json=payload)
        assert put_response.status_code == 200
        data = put_response.json()
        assert data["prompts"]["cs"] == test_prompt

        # Verify GET returns updated prompt
        get_response = client.get("/api/prompts")
        assert get_response.status_code == 200
        assert get_response.json()["prompts"]["cs"] == test_prompt
    finally:
        if orig:
            save_tenant_json("default", "prompts.json", orig)

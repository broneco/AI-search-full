import os
from fastapi.testclient import TestClient
from app.main import app
from app.core.prompts import CUSTOM_PROMPTS_FILE

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
        # Cleanup custom prompts file created during test
        if os.path.exists(CUSTOM_PROMPTS_FILE):
            os.remove(CUSTOM_PROMPTS_FILE)

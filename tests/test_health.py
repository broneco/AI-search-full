from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)


def test_health_check_endpoints():
    # Test primary health route
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["environment"] == settings.APP_ENV
    assert data["app_name"] == settings.APP_NAME
    assert "version" in data

    # Test api prefix health route
    response_api = client.get("/api/health")
    assert response_api.status_code == 200
    assert response_api.json() == data


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "Welcome" in data["message"]
    assert data["health_check"] == "/health"

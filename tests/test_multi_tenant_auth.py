import pytest
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.storage.db import get_db, SessionLocal, init_db
from app.storage.models import DBUser, DBChatThread, DBChatMessage
from app.core.config import settings

# Initialize database tables for tests
init_db()

client = TestClient(app)


def test_auth_login_demo_user():
    """Test logging in with auto-seeded demo user."""
    response = client.post(
        "/api/auth/login",
        json={"email": "user@dolphin.cz", "password": "password123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "user@dolphin.cz"
    assert data["user"]["role"] == "User"


def test_auth_register_new_user():
    """Test registering a new user in current TENANT_ID scope."""
    unique_email = f"test_{uuid.uuid4().hex[:6]}@dolphin.cz"
    response = client.post(
        "/api/auth/register",
        json={
            "email": unique_email,
            "username": "Test Uživatel",
            "password": "mysecretpassword",
            "role": "Management"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["email"] == unique_email
    assert data["user"]["role"] == "Management"
    assert "Management" in data["user"]["groups"]


def test_threads_crud_workflow():
    """Test creating, listing, renaming, and deleting chat threads."""
    # 1. Login
    login_res = client.post(
        "/api/auth/login",
        json={"email": "user@dolphin.cz", "password": "password123"}
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create thread
    create_res = client.post(
        "/api/threads",
        json={"title": "Testovací konverzace 1"},
        headers=headers
    )
    assert create_res.status_code == 200
    thread_data = create_res.json()
    thread_id = thread_data["thread_id"]
    assert thread_data["title"] == "Testovací konverzace 1"

    # 3. List threads
    list_res = client.get("/api/threads", headers=headers)
    assert list_res.status_code == 200
    threads_list = list_res.json()
    assert any(t["thread_id"] == thread_id for t in threads_list)

    # 4. Rename thread
    patch_res = client.patch(
        f"/api/threads/{thread_id}",
        json={"title": "Upravený název konverzace"},
        headers=headers
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["title"] == "Upravený název konverzace"

    # 5. Delete thread
    del_res = client.delete(f"/api/threads/{thread_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"


def test_multi_tenant_user_isolation():
    """Verify that users belonging to other tenant IDs are not returned."""
    with SessionLocal() as db:
        # Create a user under 'other_tenant'
        other_user = DBUser(
            tenant_id="other_tenant",
            email="secret@otherclient.cz",
            username="Other Client User",
            password_hash="hashedpassword",
            role="User",
            groups=["User"]
        )
        db.add(other_user)
        db.commit()

    # Attempting login with 'other_tenant' user under current 'dolphin' tenant should fail with 401
    login_res = client.post(
        "/api/auth/login",
        json={"email": "secret@otherclient.cz", "password": "hashedpassword"}
    )
    assert login_res.status_code == 401

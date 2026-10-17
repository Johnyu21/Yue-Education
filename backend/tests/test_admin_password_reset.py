"""Administrator reset works for every account type and preserves auth boundaries."""
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token, verify_password
from app.models.user import SysUser


def headers(db, user_id):
    user = db.get(SysUser, user_id)
    return {"Authorization": "Bearer " + create_access_token(user.id, user.token_version)}


@pytest.mark.parametrize("target_key", ["advisor", "head", "admin", "student_user"])
def test_admin_resets_each_account_type(m3_db, m3_env, target_key):
    target_id = m3_env[target_key]
    target = m3_db.get(SysUser, target_id)
    old_version = target.token_version
    old_token = headers(m3_db, target_id)
    with TestClient(app) as client:
        result = client.post(f"/api/v1/management/users/{target_id}/password-reset", headers=headers(m3_db, m3_env["admin"]))
        assert result.status_code == 200
        data = result.json()["data"]
        assert data["mustChangePassword"] is True
        assert len(data["temporaryPassword"]) >= 12
        m3_db.refresh(target)
        assert verify_password(data["temporaryPassword"], target.password_hash)
        assert target.token_version == old_version + 1
        assert target.must_change_password is True
        assert target.temporary_password_expires_at > datetime.now(timezone.utc)
        assert client.get("/api/v1/auth/me", headers=old_token).status_code == 401
        login = client.post("/api/v1/auth/login", json={"username": target.username, "password": data["temporaryPassword"]})
        assert login.status_code == 200
        assert login.json()["data"]["user"]["mustChangePassword"] is True
        restricted = {"Authorization": "Bearer " + login.json()["data"]["accessToken"]}
        assert client.get("/api/v1/organization/users", headers=restricted).status_code == 403


@pytest.mark.parametrize("actor_key", ["advisor", "head", "student_user"])
def test_non_admin_cannot_reset_any_account(m3_db, m3_env, actor_key):
    target = m3_db.get(SysUser, m3_env["admin"])
    old_hash, old_version = target.password_hash, target.token_version
    with TestClient(app) as client:
        response = client.post(f"/api/v1/management/users/{target.id}/password-reset", headers=headers(m3_db, m3_env[actor_key]))
        assert response.status_code == 403
    m3_db.refresh(target)
    assert target.password_hash == old_hash
    assert target.token_version == old_version


@pytest.mark.parametrize("actor_key,visible", [("admin", True), ("advisor", False), ("head", False)])
def test_directory_login_accounts_are_admin_only(m3_db, m3_env, actor_key, visible):
    with TestClient(app) as client:
        response = client.get("/api/v1/organization/users", headers=headers(m3_db, m3_env[actor_key]))
        assert response.status_code == 200
        rows = response.json()["data"]["items"]
        assert rows
        assert all(("username" in row) is visible for row in rows)
        assert all("realName" in row and "contactInfo" in row for row in rows)

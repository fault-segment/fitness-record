"""API 端点回归测试"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


class TestHealth:
    """健康检查"""

    def test_health_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestAuth:
    """认证"""

    def test_login_missing_code(self, client):
        resp = client.post("/api/auth/login", json={})
        assert resp.status_code == 400

    def test_login_invalid_code(self, client):
        resp = client.post("/api/auth/login", json={"code": "invalid_test_code"})
        # 微信会返回 errcode，不是 openid
        assert resp.status_code in (400, 502)

    def test_chat_no_auth(self, client):
        resp = client.post("/api/chat", json={"message": "你好"})
        assert resp.status_code == 401

    def test_chat_empty_message(self, client):
        from app.middleware import create_token
        token = create_token(1)
        resp = client.post(
            "/api/chat",
            json={"message": ""},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "reply" in resp.json()

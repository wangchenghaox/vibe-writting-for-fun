import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_register_and_login():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 注册
        resp = await client.post("/api/auth/register", json={"username": "testuser", "password": "test123"})
        assert resp.status_code == 200

        # 登录
        resp = await client.post("/api/auth/login", json={"username": "testuser", "password": "test123"})
        assert resp.status_code == 200
        assert "token" in resp.json()

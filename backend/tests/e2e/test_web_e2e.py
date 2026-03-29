import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_complete_user_flow():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 注册
        resp = await client.post("/api/auth/register", json={"username": "e2euser", "password": "pass123"})
        assert resp.status_code == 200

        # 登录
        resp = await client.post("/api/auth/login", json={"username": "e2euser", "password": "pass123"})
        assert resp.status_code == 200
        token = resp.json()["token"]

        # 创建小说
        resp = await client.post("/api/novels",
            json={"novel_id": "novel1", "title": "测试小说", "description": "测试描述"},
            headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

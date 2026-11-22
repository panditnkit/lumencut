import sys
import sysconfig

import pytest

if sys.platform == "win32" and sysconfig.get_platform() == "win-arm64":
    pytest.skip("FastAPI native dependencies are not supported in this Windows ARM test environment.", allow_module_level=True)

from fastapi.testclient import TestClient

import api


def test_admin_api_and_source_validation(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "DATA_DIR", tmp_path)
    monkeypatch.setattr(api, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(api, "CLIP_DIR", tmp_path / "clips")
    monkeypatch.setattr(api, "DB_PATH", tmp_path / "lumencut.sqlite3")
    monkeypatch.setattr(api, "ADMIN_USERNAME", "test-admin")
    monkeypatch.setattr(api, "ADMIN_PASSWORD", "test-password-long-enough")
    monkeypatch.setattr(api, "APP_SECRET", "test-secret-that-is-long-enough-for-fernet")
    monkeypatch.setattr(api, "SCHEDULER_STARTED", False)

    auth = ("test-admin", "test-password-long-enough")
    with TestClient(api.app) as client:
        assert client.get("/api/health").json()["ok"] is True
        dashboard = client.get("/")
        assert dashboard.status_code == 200
        assert "LumenCut" in dashboard.text
        assert client.get("/api/status").json()["ready"] is True
        assert client.post("/api/auth/check", auth=auth).json() == {"authenticated": True}
        assert client.get("/api/accounts", auth=auth).json() == {
            "youtube": {"connected": False},
            "instagram": {"connected": False},
        }
        response = client.get("/api/accounts")
        assert response.status_code == 401

        response = client.post(
            "/api/jobs",
            files={"source_url": (None, "https://example.com/private.mp4")},
            auth=auth,
        )
        assert response.status_code == 400
        assert "Only HTTPS YouTube, Twitch, and Kick URLs" in response.json()["detail"]

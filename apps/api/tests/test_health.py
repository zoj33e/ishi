from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from ishi.config import get_settings
from ishi.engine.katago_process import KataGoProcess
from ishi.main import create_app


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ISHI_DB_PATH", str(tmp_path / "ishi.db"))
    monkeypatch.setenv("ISHI_KATAGO_BIN", str(tmp_path / "missing.exe"))
    monkeypatch.setenv("ISHI_LLM_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def _get_health(engine: KataGoProcess | None) -> dict:
    app = create_app()
    app.state.engine = engine
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    return resp.json()


async def test_health_engine_down_when_not_configured() -> None:
    body = await _get_health(None)
    assert body == {
        "api": "ok",
        "engine": "down",
        "llm": "disabled",
        "db": "ok",
        "engine_version": None,
    }


async def test_health_engine_ok(fake_engine: KataGoProcess) -> None:
    body = await _get_health(fake_engine)
    assert body["engine"] == "ok"
    assert body["engine_version"] == "fake-1.0"

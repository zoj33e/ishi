import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ishi.engine.katago_process import KataGoProcess

FAKE_KATAGO = [sys.executable, "-I", str(Path(__file__).with_name("fake_katago.py"))]


@pytest.fixture
async def fake_engine() -> AsyncIterator[KataGoProcess]:
    engine = KataGoProcess(FAKE_KATAGO)
    await engine.start(ready_timeout=10)
    yield engine
    await engine.stop()


@pytest.fixture
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """App client on a fresh migrated SQLite database (no KataGo)."""
    from ishi.config import get_settings
    from ishi.db.session import migrate
    from ishi.main import create_app

    monkeypatch.setenv("ISHI_DB_PATH", str(tmp_path / "ishi.db"))
    for key in ("ISHI_KATAGO_BIN", "ISHI_KATAGO_MODEL", "ISHI_KATAGO_CONFIG"):
        monkeypatch.setenv(key, str(tmp_path / "missing"))
    get_settings.cache_clear()
    migrate(get_settings().db_path)
    with TestClient(create_app()) as client:
        yield client
    get_settings.cache_clear()

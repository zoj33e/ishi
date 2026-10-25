from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from ishi.config import get_settings
from ishi.db.session import db_ok
from ishi.engine.katago_process import KataGoProcess

router = APIRouter()


class Health(BaseModel):
    api: Literal["ok"]
    engine: Literal["ok", "down"]
    llm: Literal["ok", "disabled", "down"]
    db: Literal["ok", "down"]
    engine_version: str | None = None


@router.get("/health", response_model=Health)
async def health(request: Request) -> Health:
    settings = get_settings()
    engine: KataGoProcess | None = request.app.state.engine
    engine_ok = engine is not None and await engine.ping()
    # LLM is only reported as configured/disabled here; a live check arrives with the narrator (M5).
    llm = "ok" if settings.llm_enabled and settings.anthropic_api_key else "disabled"
    return Health(
        api="ok",
        engine="ok" if engine_ok else "down",
        llm=llm,
        db="ok" if db_ok(settings.db_path) else "down",
        engine_version=engine.version if engine_ok and engine else None,
    )

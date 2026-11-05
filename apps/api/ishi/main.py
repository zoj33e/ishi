import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ishi.api import (
    routes_games,
    routes_gym,
    routes_health,
    routes_lessons,
    routes_me,
    routes_sandbox,
    routes_school,
)
from ishi.api.errors import install_error_handlers
from ishi.config import get_settings
from ishi.db.session import migrate
from ishi.engine.katago_process import EngineError, KataGoProcess
from ishi.play.review_service import AnalysisWorker
from ishi.teacher.llm import TeacherLLM

log = logging.getLogger("ishi")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    migrate(settings.db_path)
    app.state.engine = None
    app.state.analysis = None
    app.state.teacher = None
    if settings.llm_enabled and settings.anthropic_api_key is not None:
        app.state.teacher = TeacherLLM(
            settings.anthropic_api_key.get_secret_value(), settings.llm_model
        )
    start_task: asyncio.Task[None] | None = None
    if settings.katago_configured:
        engine = KataGoProcess(settings.katago_command())
        app.state.engine = engine
        # Start in the background: the first OpenCL launch tunes kernels and can take minutes.
        start_task = asyncio.create_task(_start_engine(engine))
        # Per-move analysis + Why Engine review of full games (M4), retried until the engine is up.
        app.state.analysis = AnalysisWorker(
            settings.db_path,
            lambda: app.state.engine,
            lambda: app.state.teacher,
            settings.llm_model,
        )
        app.state.analysis.start()
    else:
        log.warning("KataGo not configured (run scripts/setup_engine.ps1); engine offline")
    yield
    if app.state.analysis is not None:
        await app.state.analysis.stop()
    if start_task is not None:
        start_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await start_task
    if app.state.engine is not None:
        await app.state.engine.stop()
    if app.state.teacher is not None:
        await app.state.teacher.close()


async def _start_engine(engine: KataGoProcess) -> None:
    try:
        await engine.start()
    except (EngineError, OSError, TimeoutError) as e:
        log.error("KataGo failed to start: %s", e)


def create_app() -> FastAPI:
    app = FastAPI(title="Ishi API", version="0.1.0", lifespan=lifespan)
    app.state.engine = None
    app.state.analysis = None
    app.state.teacher = None
    app.include_router(routes_health.router, prefix="/api")
    app.include_router(routes_sandbox.router, prefix="/api")
    app.include_router(routes_me.router, prefix="/api")
    app.include_router(routes_school.router, prefix="/api")
    app.include_router(routes_games.router, prefix="/api")
    app.include_router(routes_lessons.router, prefix="/api")
    app.include_router(routes_gym.router, prefix="/api")

    install_error_handlers(app)
    return app


app = create_app()

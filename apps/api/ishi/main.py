import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ishi.api import routes_games, routes_health, routes_me, routes_sandbox, routes_school
from ishi.api.errors import install_error_handlers
from ishi.config import get_settings
from ishi.db.session import migrate
from ishi.engine.katago_process import EngineError, KataGoProcess

log = logging.getLogger("ishi")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    migrate(settings.db_path)
    app.state.engine = None
    start_task: asyncio.Task[None] | None = None
    if settings.katago_configured:
        engine = KataGoProcess(settings.katago_command())
        app.state.engine = engine
        # Start in the background: the first OpenCL launch tunes kernels and can take minutes.
        start_task = asyncio.create_task(_start_engine(engine))
    else:
        log.warning("KataGo not configured (run scripts/setup_engine.ps1); engine offline")
    yield
    if start_task is not None:
        start_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await start_task
    if app.state.engine is not None:
        await app.state.engine.stop()


async def _start_engine(engine: KataGoProcess) -> None:
    try:
        await engine.start()
    except (EngineError, OSError, TimeoutError) as e:
        log.error("KataGo failed to start: %s", e)


def create_app() -> FastAPI:
    app = FastAPI(title="Ishi API", version="0.1.0", lifespan=lifespan)
    app.state.engine = None
    app.include_router(routes_health.router, prefix="/api")
    app.include_router(routes_sandbox.router, prefix="/api")
    app.include_router(routes_me.router, prefix="/api")
    app.include_router(routes_school.router, prefix="/api")
    app.include_router(routes_games.router, prefix="/api")

    install_error_handlers(app)
    return app


app = create_app()

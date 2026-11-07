import logging
import signal
import sys
import traceback
from typing import Any, Dict

from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from .config import settings, BASE_DIR, STORAGE_DIR
from .logging_config import configure_logging
from .routes import router as api_router
from .websocket_manager import ws_manager
from .rate_limiter import check_rate_limit


configure_logging()
logger = logging.getLogger("backend")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Emotion-Aware Smart Street Lighting - Backend",
        description="Central monitoring station API (Phase 3 - production-grade).",
        version="3.0.0",
    )

    # CORS configuration for dashboard and external clients
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOW_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount static frontend if available (e.g. built dist or unified deployment)
    frontend_path = BASE_DIR.parent / "frontend"
    dist_path = frontend_path / "dist"
    static_frontend_dir = dist_path if dist_path.exists() else (frontend_path if frontend_path.exists() else None)
    if static_frontend_dir and static_frontend_dir.exists():
        app.mount("/frontend", StaticFiles(directory=str(static_frontend_dir), html=True), name="frontend")

    # Serve storage directory (snapshots, models) as static files
    app.mount("/storage", StaticFiles(directory=str(STORAGE_DIR), html=False), name="storage")

    @app.get("/")
    async def root() -> Dict[str, Any]:
        return {
            "message": "Emotion-Aware Smart Street Lighting Backend (Phase 3)",
            "docs": "/docs",
        }

    app.include_router(api_router)

    @app.websocket("/ws/dashboard")
    async def websocket_dashboard(websocket: WebSocket) -> None:
        await ws_manager.connect(websocket)
        try:
            while True:
                # Keep the connection alive; dashboard clients do not need to send messages
                await websocket.receive_text()
        except Exception:
            ws_manager.disconnect(websocket)

    # Global error-handling middleware
    @app.middleware("http")
    async def error_handling_middleware(request: Request, call_next):
        # Rate limiting
        allowed, endpoint_id = check_rate_limit(request)
        if not allowed:
            logger.warning(
                "Rate limit exceeded for %s on %s", request.client.host, endpoint_id
            )
            return JSONResponse(
                status_code=429,
                content={"success": False, "error": "Too many requests"},
            )

        try:
            response = await call_next(request)
            return response
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Unhandled exception for %s %s: %s\n%s",
                request.method,
                request.url.path,
                exc,
                traceback.format_exc(),
            )
            # Hardened error response in production
            body: Dict[str, Any] = {"success": False, "error": "Internal server error"}
            return JSONResponse(status_code=500, content=body)

    return app


app = create_app()


def _graceful_shutdown(*_: Any) -> None:
    logger.info("Received shutdown signal. Stopping backend gracefully.")
    sys.exit(0)


def main() -> None:
    logger.info("=" * 60)
    logger.info("Emotion-Aware Smart Street Lighting System")
    logger.info("Central Monitoring Station - Phase 4 (Final)")
    logger.info("Environment: %s", settings.ENV)
    logger.info("Version: %s", settings.SYSTEM_VERSION)
    logger.info("=" * 60)
    logger.info(
        "Server starting on http://%s:%s", settings.HOST, settings.PORT
    )

    signal.signal(signal.SIGINT, _graceful_shutdown)
    signal.signal(signal.SIGTERM, _graceful_shutdown)

    if settings.is_production:
        # In production enforce non-debug, no auto-reload
        reload = False
    else:
        reload = settings.DEBUG

    if settings.is_production and (not settings.SECRET_KEY or len(settings.SECRET_KEY) < 16):
        logger.error("SECRET_KEY is too short or not set in production.")
        sys.exit(1)

    uvicorn.run(
        "backend.app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=reload,
    )


if __name__ == "__main__":
    main()
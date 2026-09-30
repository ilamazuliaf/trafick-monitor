"""
FastAPI Application Entry Point (prd.md Section 41 & 51)
Manages application startup lifecycle, database initialization, background worker,
REST API routers, and static frontend file serving.
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.logging import logger
from app.database.database import init_db
from app.mikrotik.collector import collector

from app.api.routes_config import router as config_router
from app.api.routes_status import router as status_router
from app.api.routes_interfaces import router as interfaces_router
from app.api.routes_traffic import router as traffic_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup & shutdown lifespan context manager.
    (prd.md Section 51 - Startup Validation & Initialization Flow)
    """
    logger.info("=============================================")
    logger.info(" Starting MikroTik Traffic Monitor App")
    logger.info("=============================================")

    # 1. Initialize SQLite Database Schema
    init_db()

    # 2. Start Background Traffic Collector Worker (Single Worker)
    await collector.start()

    yield  # Application runs

    # 3. Shutdown Traffic Collector Worker
    logger.info("Shutting down application background tasks...")
    await collector.stop()
    logger.info("Application shutdown complete.")


app = FastAPI(
    title="MikroTik Traffic Monitor API",
    description="Configuration-driven RouterOS traffic monitoring REST API",
    version="1.0.0",
    lifespan=lifespan
)

# Register REST API Routers
app.include_router(config_router)
app.include_router(status_router)
app.include_router(interfaces_router)
app.include_router(traffic_router)

# Mount Static Frontend Files (prd.md Section 5, 32, 41)
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        index_path = os.path.join(frontend_dir, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"message": "MikroTik Traffic Monitor API is running."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.web_host,
        port=settings.web_port,
        reload=False
    )

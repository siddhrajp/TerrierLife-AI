import logging
import os
import time
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.db.connection import engine
from app.limiter import limiter
from app.routes import events, places, query, resources

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="TerrierLife AI API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ALLOWED_ORIGINS = comma-separated list in env, e.g.:
# "http://localhost:3000,https://terrierlife-ai.vercel.app"
_origins_env = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
allowed_origins = [o.strip() for o in _origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    """Tag every request with an id and log its outcome, so a user-reported
    failure can be traced to a specific request in the logs."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
    started = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "request_failed",
            extra={"request_id": request_id, "path": request.url.path},
        )
        return JSONResponse(status_code=500, content={"detail": "Something went wrong."})

    elapsed_ms = round((time.monotonic() - started) * 1000)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_complete path=%s status=%s elapsed_ms=%s request_id=%s",
        request.url.path,
        response.status_code,
        elapsed_ms,
        request_id,
    )
    return response


app.include_router(query.router, prefix="/api")
app.include_router(places.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(resources.router, prefix="/api")


@app.get("/health")
def health():
    """Liveness only — always 200 if the process is up."""
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """Readiness — verifies dependencies an orchestrator should route traffic on.
    Distinct from /health so a broken database takes an instance out of
    rotation instead of quietly serving errors."""
    checks = {"database": False, "openai_key": bool(os.getenv("OPENAI_API_KEY"))}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        logger.exception("readiness_db_check_failed")

    ok = all(checks.values())
    return JSONResponse(
        status_code=200 if ok else 503,
        content={"status": "ready" if ok else "not ready", "checks": checks},
    )

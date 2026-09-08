import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from openai import APITimeoutError, AuthenticationError, RateLimitError
from pydantic import BaseModel, Field

from app.db.connection import get_db
from app.limiter import DEFAULT_QUERY_LIMIT, limiter
from app.services.memory_service import clear_history
from app.services.openai_service import handle_query

logger = logging.getLogger(__name__)

router = APIRouter()


class QueryRequest(BaseModel):
    # Unbounded input goes straight to a paid model, so every field is capped.
    message: str = Field(min_length=1, max_length=1000)
    location: str | None = Field(default=None, max_length=100)   # e.g. "CDS", "CAS", "GSU"
    time_available: int | None = Field(default=None, ge=1, le=1440)  # minutes
    interests: list[str] | None = Field(default=None, max_length=20)
    # Opt-in conversation memory. Omit it and the request stays stateless.
    session_id: str | None = Field(default=None, max_length=100)


@router.post("/query")
@limiter.limit(DEFAULT_QUERY_LIMIT)
async def query(request: Request, req: QueryRequest, db=Depends(get_db)):
    try:
        return await handle_query(
            message=req.message,
            location=req.location,
            time_available=req.time_available,
            interests=req.interests,
            db=db,
            session_id=req.session_id,
        )
    # `from None` throughout: the original exception is logged server-side, but
    # suppressing the chain keeps provider internals out of the client response.
    except RateLimitError:
        raise HTTPException(
            status_code=429,
            detail="The assistant is busy right now. Please try again in a moment.",
        ) from None
    except AuthenticationError:
        logger.error("openai_auth_failed")
        raise HTTPException(
            status_code=503, detail="Assistant temporarily unavailable."
        ) from None
    except (TimeoutError, APITimeoutError):
        logger.warning("agent_timeout", extra={"message_len": len(req.message)})
        raise HTTPException(
            status_code=504,
            detail="That took too long to answer. Try a more specific question.",
        ) from None
    except Exception:
        # Never surface raw exception text — it can leak connection strings,
        # prompts, and provider internals to the client.
        logger.exception("query_failed")
        raise HTTPException(status_code=500, detail="Something went wrong.") from None


@router.delete("/query/history/{session_id}")
async def delete_history(session_id: str, db=Depends(get_db)):
    """Let a user drop their conversation. Anyone holding a session id can
    clear it — the ids are client-generated and unauthenticated, so this
    grants no more access than sending queries with that id already does."""
    removed = clear_history(db, session_id)
    return {"deleted_messages": removed}

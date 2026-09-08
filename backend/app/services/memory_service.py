"""Conversation history for multi-turn queries.

Persisted in Postgres rather than LangGraph's in-memory checkpointer, which
would lose state on restart and isn't shared across instances.

Every stored turn is re-sent to the model on each subsequent request, so
history is bounded on two axes — number of messages and characters per
message. Without both, a long session grows the prompt (and its cost)
without limit.
"""
import logging
import os

from sqlalchemy.orm import Session

from app.models.db_models import ConversationMessage

logger = logging.getLogger(__name__)

# Turns kept in context. 6 messages ≈ 3 exchanges — enough for "actually,
# closer to Questrom" to resolve, without dragging a whole session along.
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "6"))

# Per-message cap. Assistant answers can be long; replaying them verbatim is
# the main way history inflates a prompt.
MAX_MESSAGE_CHARS = int(os.getenv("MAX_HISTORY_MESSAGE_CHARS", "1500"))


def load_history(db: Session, session_id: str | None) -> list[dict]:
    """Most recent messages for a session, oldest first.

    Returns [] for an absent session_id, which keeps the endpoint's original
    stateless behaviour for callers that don't opt in.
    """
    if not session_id:
        return []

    rows = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.session_id == session_id)
        .order_by(ConversationMessage.created_at.desc(), ConversationMessage.id.desc())
        .limit(MAX_HISTORY_MESSAGES)
        .all()
    )

    # Queried newest-first to get the *latest* N, but the model needs
    # chronological order.
    return [
        {"role": r.role, "content": (r.content or "")[:MAX_MESSAGE_CHARS]}
        for r in reversed(rows)
    ]


def save_turn(db: Session, session_id: str | None, user_message: str, assistant_message: str) -> None:
    """Append one exchange. Never raises — losing history is a degraded
    experience, but failing the request the user already paid for is worse."""
    if not session_id:
        return

    try:
        db.add_all([
            ConversationMessage(
                session_id=session_id, role="user", content=user_message[:MAX_MESSAGE_CHARS]
            ),
            ConversationMessage(
                session_id=session_id, role="assistant", content=assistant_message[:MAX_MESSAGE_CHARS]
            ),
        ])
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("conversation_history_save_failed", extra={"session_id": session_id})


def clear_history(db: Session, session_id: str) -> int:
    """Delete a session's history. Returns rows removed."""
    deleted = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.session_id == session_id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted

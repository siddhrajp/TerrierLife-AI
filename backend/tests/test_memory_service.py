"""Conversation history: ordering, bounding, and failure behaviour.

History is replayed into every subsequent request, so the caps here are cost
controls, not cosmetics.
"""
import pytest

from app.services import memory_service
from app.services.memory_service import load_history, save_turn


class FakeRow:
    def __init__(self, role, content, id_=0):
        self.role = role
        self.content = content
        self.id = id_


class FakeQuery:
    def __init__(self, rows):
        self._rows = rows
        self.limit_arg = None

    def filter(self, *_a):
        return self

    def order_by(self, *_a):
        return self

    def limit(self, n):
        self.limit_arg = n
        self._rows = self._rows[:n]
        return self

    def all(self):
        return self._rows


class FakeDB:
    def __init__(self, rows=None):
        self.q = FakeQuery(rows or [])
        self.added = []
        self.committed = False
        self.rolled_back = False
        self.commit_error = None

    def query(self, _model):
        return self.q

    def add_all(self, items):
        self.added.extend(items)

    def commit(self):
        if self.commit_error:
            raise self.commit_error
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class TestLoadHistory:
    def test_no_session_id_returns_empty(self):
        """Callers that don't opt in keep the original stateless behaviour."""
        assert load_history(FakeDB(), None) == []
        assert load_history(FakeDB(), "") == []

    def test_returns_oldest_first(self):
        # The query fetches newest-first to get the latest N; the model needs
        # chronological order, so the result must be reversed.
        db = FakeDB([FakeRow("assistant", "second"), FakeRow("user", "first")])
        assert [m["content"] for m in load_history(db, "s1")] == ["first", "second"]

    def test_caps_number_of_messages(self):
        db = FakeDB([FakeRow("user", f"m{i}") for i in range(50)])
        load_history(db, "s1")
        assert db.q.limit_arg == memory_service.MAX_HISTORY_MESSAGES

    def test_truncates_long_messages(self, monkeypatch):
        monkeypatch.setattr(memory_service, "MAX_MESSAGE_CHARS", 10)
        db = FakeDB([FakeRow("assistant", "x" * 500)])
        assert len(load_history(db, "s1")[0]["content"]) == 10

    def test_handles_null_content(self):
        db = FakeDB([FakeRow("user", None)])
        assert load_history(db, "s1")[0]["content"] == ""

    def test_preserves_roles(self):
        db = FakeDB([FakeRow("assistant", "a"), FakeRow("user", "q")])
        assert [m["role"] for m in load_history(db, "s1")] == ["user", "assistant"]


class TestSaveTurn:
    def test_no_session_id_writes_nothing(self):
        db = FakeDB()
        save_turn(db, None, "q", "a")
        assert db.added == [] and not db.committed

    def test_persists_both_sides_of_the_exchange(self):
        db = FakeDB()
        save_turn(db, "s1", "question", "answer")
        assert [m.role for m in db.added] == ["user", "assistant"]
        assert db.committed

    def test_truncates_before_storing(self, monkeypatch):
        monkeypatch.setattr(memory_service, "MAX_MESSAGE_CHARS", 5)
        db = FakeDB()
        save_turn(db, "s1", "x" * 100, "y" * 100)
        assert all(len(m.content) == 5 for m in db.added)

    def test_db_failure_does_not_raise(self):
        """The user already paid for this answer — losing history is better
        than failing the request after the model call succeeded."""
        db = FakeDB()
        db.commit_error = RuntimeError("connection lost")
        save_turn(db, "s1", "q", "a")   # must not raise
        assert db.rolled_back


@pytest.mark.asyncio
class TestHistoryReachesTheAgent:
    async def test_history_is_replayed_between_system_prompt_and_query(self, monkeypatch):
        """Guards the wiring: loading history is useless if handle_query
        doesn't put it in the message list."""
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

        from app.services import openai_service

        monkeypatch.setattr(
            openai_service, "load_history",
            lambda _db, _sid: [
                {"role": "user", "content": "study spot near CAS"},
                {"role": "assistant", "content": "Try Mugar Library."},
            ],
        )
        monkeypatch.setattr(openai_service, "save_turn", lambda *_a, **_k: None)

        captured = {}

        class FakeAgent:
            async def ainvoke(self, payload, config=None):
                captured["messages"] = payload["messages"]
                return {"messages": [AIMessage(content="ok")]}

        monkeypatch.setattr(openai_service, "create_react_agent", lambda *_a, **_k: FakeAgent())

        await openai_service.handle_query(
            message="somewhere closer to Questrom",
            location=None, time_available=None, interests=None,
            db=None, session_id="s1",
        )

        msgs = captured["messages"]
        assert isinstance(msgs[0], SystemMessage)
        assert isinstance(msgs[1], HumanMessage) and "study spot near CAS" in msgs[1].content
        assert isinstance(msgs[2], AIMessage) and "Mugar" in msgs[2].content
        # Current query goes last, after the replayed turns.
        assert "Questrom" in msgs[-1].content

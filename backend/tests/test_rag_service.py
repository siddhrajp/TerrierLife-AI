"""Corpus loading, chunking config, and context assembly.

Covers the two retrieval bugs found in the eval audit: URL-level dedup that
collapsed distinct chunks from one page, and a truncation that dropped content
the answer depended on.
"""
import json

import pytest

from app.services import rag_service


@pytest.fixture
def corpus_file(tmp_path, monkeypatch):
    """Point the loader at a temporary corpus instead of the real one."""
    data = [
        {
            "title": "OPT Guide",
            "url": "https://bu.edu/isso/opt",
            "category": "international",
            "content": "A" * 2000,
        },
        {
            "title": "Career Center",
            "url": "https://bu.edu/careers",
            "category": "career",
            "content": "B" * 500,
        },
    ]
    path = tmp_path / "bu_resources.json"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(
        rag_service.os.path, "join", lambda *_args: str(path)
    )
    return path


class TestLoadResourceChunks:
    def test_returns_whole_pages_when_chunking_disabled(self, corpus_file, monkeypatch):
        monkeypatch.setattr(rag_service, "CHUNK_SIZE", 0)
        docs = rag_service.load_resource_chunks()
        assert len(docs) == 2

    def test_splits_pages_when_chunk_size_set(self, corpus_file, monkeypatch):
        monkeypatch.setattr(rag_service, "CHUNK_SIZE", 400)
        monkeypatch.setattr(rag_service, "CHUNK_OVERLAP", 0)
        docs = rag_service.load_resource_chunks()
        # 2000-char doc splits into several; 500-char doc into at least one.
        assert len(docs) > 2
        assert all(len(d.page_content) <= 400 for d in docs)

    def test_preserves_source_metadata_through_chunking(self, corpus_file, monkeypatch):
        monkeypatch.setattr(rag_service, "CHUNK_SIZE", 400)
        docs = rag_service.load_resource_chunks()
        for doc in docs:
            assert doc.metadata["url"]
            assert doc.metadata["title"]
            assert doc.metadata["category"]

    def test_missing_corpus_returns_empty_not_error(self, monkeypatch):
        # A missing corpus must degrade to vector-only retrieval, not crash the
        # request path.
        monkeypatch.setattr(rag_service.os.path, "exists", lambda _p: False)
        assert rag_service.load_resource_chunks() == []


class FakeDoc:
    def __init__(self, content, url, title="T", category="c"):
        self.page_content = content
        self.metadata = {"url": url, "title": title, "category": category}


class FakeRetriever:
    def __init__(self, docs):
        self._docs = docs

    def invoke(self, _query):
        return self._docs


@pytest.mark.asyncio
class TestSearchBUResources:
    async def _run(self, monkeypatch, docs):
        monkeypatch.setattr(rag_service, "load_resource_chunks", lambda: [])
        monkeypatch.setattr(
            rag_service, "_get_vectorstore",
            lambda: type("VS", (), {"as_retriever": lambda self, **_k: FakeRetriever(docs)})(),
        )
        return await rag_service.search_bu_resources(db=None, query="q")

    async def test_keeps_distinct_chunks_from_the_same_page(self, monkeypatch):
        """Dedup is per-chunk, not per-URL — several chunks of one page can
        each be relevant, and URL-dedup would discard all but the first."""
        docs = [
            FakeDoc("chunk one", "https://bu.edu/a"),
            FakeDoc("chunk two", "https://bu.edu/a"),
        ]
        result = await self._run(monkeypatch, docs)
        assert len(result["chunks"]) == 2
        # Citations still collapse to one entry per page.
        assert len(result["sources"]) == 1

    async def test_drops_exact_duplicate_chunks(self, monkeypatch):
        # BM25 and vector search frequently return the same chunk.
        docs = [FakeDoc("same", "https://bu.edu/a"), FakeDoc("same", "https://bu.edu/a")]
        result = await self._run(monkeypatch, docs)
        assert len(result["chunks"]) == 1

    async def test_context_is_not_truncated(self, monkeypatch):
        """Regression: content past a fixed cutoff used to be dropped, so
        answers were graded against text the model never received."""
        long_content = "X" * 3000
        result = await self._run(monkeypatch, [FakeDoc(long_content, "https://bu.edu/a")])
        assert long_content in result["context"]

    async def test_empty_retrieval_returns_graceful_message(self, monkeypatch):
        result = await self._run(monkeypatch, [])
        assert result["sources"] == []
        assert "No relevant" in result["context"]

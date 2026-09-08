import os

from dotenv import load_dotenv
from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import PGVector
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy.orm import Session

load_dotenv()

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
CONNECTION_STRING = os.getenv("DATABASE_URL", "postgresql://localhost/terrierlife")

# Chunking is off by default: ablation showed no gain on this corpus (scraped
# BU pages average ~4.2k chars and are already roughly passage-sized, so
# splitting them cost recall without improving precision). Set RAG_CHUNK_SIZE
# to re-enable it for comparison runs.
CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "0"))  # 0 = index whole pages
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "100"))


def _get_vectorstore() -> PGVector:
    return PGVector(
        connection_string=CONNECTION_STRING,
        embedding_function=embeddings,
        collection_name="bu_resources",
        use_jsonb=True,
    )


def load_resource_chunks() -> list[Document]:
    """Load BU resources and split them into chunks.

    Shared by the embedding pipeline (scripts/build_embeddings.py) and the
    BM25 retriever below, so both index identical units."""
    import json
    data_path = os.path.join(os.path.dirname(__file__), "../../../data/bu_resources.json")
    if not os.path.exists(data_path):
        return []
    with open(data_path) as f:
        resources = json.load(f)
    docs = [
        Document(
            page_content=f"{r['title']}. {r['content']}",
            metadata={"title": r["title"], "url": r["url"], "category": r["category"]},
        )
        for r in resources
    ]
    if CHUNK_SIZE <= 0:
        return docs

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    return splitter.split_documents(docs)


async def search_bu_resources(db: Session, query: str) -> dict:
    # Vector retriever — semantic similarity
    vectorstore = _get_vectorstore()
    vector_retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

    # BM25 retriever — keyword matching
    all_docs = load_resource_chunks()
    if all_docs:
        bm25_retriever = BM25Retriever.from_documents(all_docs, k=5)

        # Ensemble: 40% BM25 keyword + 60% vector semantic
        retriever = EnsembleRetriever(
            retrievers=[bm25_retriever, vector_retriever],
            weights=[0.4, 0.6],
        )
    else:
        retriever = vector_retriever

    docs = retriever.invoke(query)

    if not docs:
        return {
            "context": "No relevant BU resources found.",
            "sources": [],
        }

    # Deduplicate identical chunks (BM25 and vector search often return the
    # same one). Dedup on content, not URL — several chunks from the same page
    # can each be relevant.
    seen_chunks = set()
    unique_docs = []
    for doc in docs:
        if doc.page_content not in seen_chunks:
            seen_chunks.add(doc.page_content)
            unique_docs.append(doc)

    top_docs = unique_docs[:4]

    # Chunks are already passage-sized, so pass them through whole rather than
    # truncating mid-answer.
    context = "\n\n".join([
        f"Source: {doc.metadata.get('title', 'BU Resource')} ({doc.metadata.get('url', '')})\n{doc.page_content}"
        for doc in top_docs
    ])

    # Citations are per-page, so collapse chunks back down by URL here.
    sources = []
    seen_urls = set()
    for doc in top_docs:
        url = doc.metadata.get("url", "")
        if url in seen_urls:
            continue
        seen_urls.add(url)
        sources.append({
            "title": doc.metadata.get("title", "BU Resource"),
            "url": url,
            "category": doc.metadata.get("category", ""),
        })

    return {
        "context": context,
        "chunks": [doc.page_content for doc in top_docs],
        "sources": sources,
    }

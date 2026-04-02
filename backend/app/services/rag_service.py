import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import PGVector
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever
from langchain_core.documents import Document
from sqlalchemy.orm import Session

load_dotenv()

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
CONNECTION_STRING = os.getenv("DATABASE_URL", "postgresql://localhost/terrierlife")


def _get_vectorstore() -> PGVector:
    return PGVector(
        connection_string=CONNECTION_STRING,
        embedding_function=embeddings,
        collection_name="bu_resources",
        use_jsonb=True,
    )


def _load_all_docs() -> list[Document]:
    """Load all documents from PGVector for BM25 indexing."""
    import json
    data_path = os.path.join(os.path.dirname(__file__), "../../../data/bu_resources.json")
    if not os.path.exists(data_path):
        return []
    with open(data_path) as f:
        resources = json.load(f)
    return [
        Document(
            page_content=f"{r['title']}. {r['content']}",
            metadata={"title": r["title"], "url": r["url"], "category": r["category"]},
        )
        for r in resources
    ]


async def search_bu_resources(db: Session, query: str) -> dict:
    # Vector retriever — semantic similarity
    vectorstore = _get_vectorstore()
    vector_retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

    # BM25 retriever — keyword matching
    all_docs = _load_all_docs()
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

    # Deduplicate by URL
    seen_urls = set()
    unique_docs = []
    for doc in docs:
        url = doc.metadata.get("url", "")
        if url not in seen_urls:
            seen_urls.add(url)
            unique_docs.append(doc)

    context = "\n\n".join([
        f"Source: {doc.metadata.get('title', 'BU Resource')} ({doc.metadata.get('url', '')})\n{doc.page_content[:1000]}"
        for doc in unique_docs[:3]
    ])

    return {
        "context": context,
        "sources": [
            {
                "title": doc.metadata.get("title", "BU Resource"),
                "url": doc.metadata.get("url", ""),
                "category": doc.metadata.get("category", ""),
            }
            for doc in unique_docs[:3]
        ],
    }

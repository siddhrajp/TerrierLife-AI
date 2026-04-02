"""
Build and store embeddings for places and BU resources using LangChain + PGVector.
Run after scrape_bu_resources.py and seed_data.py.
Usage: cd backend && python scripts/build_embeddings.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv

load_dotenv()

from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import PGVector
from langchain_core.documents import Document
from app.db.connection import SessionLocal
from app.models.db_models import Place

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
CONNECTION_STRING = os.getenv("DATABASE_URL", "postgresql://localhost/terrierlife")

db = SessionLocal()

# ── BU Resources → PGVector collection "bu_resources" ─────────────────────────
resources_path = os.path.join(os.path.dirname(__file__), "../../data/bu_resources.json")
if os.path.exists(resources_path):
    with open(resources_path) as f:
        resources = json.load(f)

    docs = [
        Document(
            page_content=f"{r['title']}. {r['content']}",
            metadata={"title": r["title"], "url": r["url"], "category": r["category"]},
        )
        for r in resources
    ]

    print(f"Storing {len(docs)} BU resource embeddings via LangChain PGVector...")
    PGVector.from_documents(
        documents=docs,
        embedding=embeddings,
        collection_name="bu_resources",
        connection_string=CONNECTION_STRING,
        pre_delete_collection=True,  # re-run safe: clears old embeddings first
    )
    print("BU resources done.")
else:
    print("No bu_resources.json found. Run scrape_bu_resources.py first.")

# ── Places → store embeddings back on Place rows ───────────────────────────────
places = db.query(Place).all()
places_without_embedding = [p for p in places if p.embedding is None]

if places_without_embedding:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    for place in places_without_embedding:
        print(f"Embedding place: {place.name}")
        text = f"{place.name}. {place.description}. Features: {', '.join(place.features or [])}"
        response = client.embeddings.create(input=text[:8000], model="text-embedding-3-small")
        place.embedding = response.data[0].embedding

    db.commit()
    print(f"Embedded {len(places_without_embedding)} places.")
else:
    print("All places already have embeddings, skipping.")

db.close()
print("Done.")

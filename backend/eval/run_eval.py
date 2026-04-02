"""
RAGAS evaluation pipeline for TerrierLife AI RAG system.

Measures:
- Faithfulness: does the answer stick to retrieved docs (no hallucination)?
- Answer Relevance: does the answer actually address the question?
- Context Precision: are the retrieved docs relevant to the question?
- Context Recall: did we retrieve all the docs needed to answer?

Usage:
    cd backend
    python eval/run_eval.py
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from datasets import Dataset
from ragas import evaluate
from ragas.metrics._faithfulness import Faithfulness
from ragas.metrics._answer_relevance import ResponseRelevancy
from ragas.metrics._context_precision import LLMContextPrecisionWithoutReference
from ragas.metrics._context_recall import LLMContextRecall
from ragas.llms import llm_factory
from ragas.embeddings import OpenAIEmbeddings as RagasOpenAIEmbeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.db.connection import SessionLocal
from app.services.rag_service import search_bu_resources
from eval.test_questions import TEST_QUESTIONS


async def collect_rag_outputs() -> list[dict]:
    """Run each test question through the RAG pipeline and collect results."""
    db = SessionLocal()
    results = []

    print(f"Running {len(TEST_QUESTIONS)} questions through RAG pipeline...\n")

    for i, test in enumerate(TEST_QUESTIONS):
        question = test["question"]
        print(f"[{i+1}/{len(TEST_QUESTIONS)}] {question}")

        try:
            result = await search_bu_resources(db=db, query=question)

            contexts = [
                f"{s.get('title', '')}: {result['context'][:500]}"
                for s in result.get("sources", [])
            ] if result.get("sources") else ["No context retrieved"]

            # Generate answer using GPT-4o grounded in retrieved context
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model="gpt-4o", temperature=0)
            prompt = f"""Answer the following question using ONLY the context provided.
If the context doesn't contain enough information, say so clearly.

Context:
{result.get('context', 'No context available')}

Question: {question}

Answer:"""
            response = llm.invoke(prompt)
            answer = response.content

            results.append({
                "question": question,
                "answer": answer,
                "contexts": contexts,
                "ground_truth": test["ground_truth"],
            })

        except Exception as e:
            print(f"  Error: {e}")
            results.append({
                "question": question,
                "answer": "Error generating answer",
                "contexts": ["Error retrieving context"],
                "ground_truth": test["ground_truth"],
            })

    db.close()
    return results


def run_ragas(results: list[dict]):
    """Run RAGAS evaluation on collected results."""
    print("\nRunning RAGAS evaluation...")

    from openai import OpenAI as OpenAIClient
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from langchain_openai import OpenAIEmbeddings as LCOpenAIEmbeddings

    openai_client = OpenAIClient(api_key=os.getenv("OPENAI_API_KEY"))
    llm = llm_factory("gpt-4o", client=openai_client)
    embeddings = LangchainEmbeddingsWrapper(LCOpenAIEmbeddings(model="text-embedding-3-small"))

    metrics = [
        Faithfulness(llm=llm),
        ResponseRelevancy(llm=llm, embeddings=embeddings),
        LLMContextPrecisionWithoutReference(llm=llm),
        LLMContextRecall(llm=llm),
    ]

    dataset = Dataset.from_list(results)

    scores = evaluate(
        dataset=dataset,
        metrics=metrics,
    )

    return scores


def print_report(scores, results: list[dict]):
    """Print a clean evaluation report."""

    # RAGAS EvaluationResult — extract mean scores from the result
    scores_df = scores.to_pandas()

    print("Score columns found:", list(scores_df.columns))
    f_score  = float(scores_df["faithfulness"].mean()) if "faithfulness" in scores_df.columns else 0.0
    ar_score = float(scores_df["answer_relevancy"].mean()) if "answer_relevancy" in scores_df.columns else 0.0
    cp_score = float(scores_df["llm_context_precision_without_reference"].mean()) if "llm_context_precision_without_reference" in scores_df.columns else 0.0
    cr_score = float(scores_df["context_recall"].mean()) if "context_recall" in scores_df.columns else 0.0

    print("\n" + "="*50)
    print("TERRIERLIFE AI — RAG EVALUATION REPORT")
    print("="*50)
    print(f"Questions evaluated: {len(results)}")
    print()
    print(f"  Faithfulness:       {f_score:.2f}  (does answer stick to retrieved docs?)")
    print(f"  Answer Relevance:   {ar_score:.2f}  (does answer address the question?)")
    print(f"  Context Precision:  {cp_score:.2f}  (are retrieved docs relevant?)")
    print(f"  Context Recall:     {cr_score:.2f}  (did we retrieve enough docs?)")
    print()

    valid_scores = [s for s in [f_score, ar_score, cp_score, cr_score] if not (s != s)]  # filter nan
    avg = sum(valid_scores) / len(valid_scores) if valid_scores else 0.0

    if avg >= 0.85:
        rating = "Excellent"
    elif avg >= 0.70:
        rating = "Good"
    elif avg >= 0.55:
        rating = "Needs improvement"
    else:
        rating = "Poor — consider expanding corpus"

    print(f"  Overall average:    {avg:.2f}  ({rating})")
    print("="*50)

    # Save results to JSON for README
    report = {
        "questions_evaluated": len(results),
        "faithfulness": round(f_score, 2),
        "answer_relevancy": round(ar_score, 2),
        "context_precision": round(cp_score, 2),
        "context_recall": round(cr_score, 2),
        "overall_average": round(avg, 2),
        "rating": rating,
    }

    out_path = os.path.join(os.path.dirname(__file__), "eval_results.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nResults saved to eval/eval_results.json")
    return report


async def main():
    # Cache RAG outputs so re-runs don't repeat API calls
    cache_path = os.path.join(os.path.dirname(__file__), "rag_outputs_cache.json")

    if os.path.exists(cache_path):
        print(f"Loading cached RAG outputs from {cache_path}")
        with open(cache_path) as f:
            results = json.load(f)
    else:
        results = await collect_rag_outputs()
        with open(cache_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"RAG outputs cached to {cache_path}")

    scores = run_ragas(results)
    print_report(scores, results)


if __name__ == "__main__":
    asyncio.run(main())

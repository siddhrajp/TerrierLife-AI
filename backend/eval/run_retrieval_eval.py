"""Deterministic retrieval evaluation — hit@k and MRR.

Why this exists
---------------
RAGAS judges with an LLM. That makes it nondeterministic (measured noise floor:
~±0.05 at n=20, see Cycle 9) and expensive enough that you cannot run it in a
loop. The consequence was that no retrieval parameter in this system had ever
been tuned empirically — k, the BM25/vector split, and the top-N cutoff were all
picked by reasoning and left alone, because there was no affordable way to tell
a real improvement from judge noise.

This harness closes that gap. Given a query and a set of known-relevant URLs,
"did the right page come back, and how high did it rank" is a set-membership
question. No judge, no sampling, and repeatable.

It is not entirely free — vector retrieval embeds the query, one
text-embedding-3-small call per question — but that is deterministic for
identical input and roughly three orders of magnitude cheaper than a RAGAS run.

This complements RAGAS rather than replacing it: retrieval quality is a
precondition for answer quality, not a substitute. A perfect hit@1 says nothing
about whether the generated answer was faithful.

Usage:
    cd backend
    python eval/run_retrieval_eval.py                    # current defaults
    python eval/run_retrieval_eval.py --mode vector      # ablate hybrid search
    python eval/run_retrieval_eval.py --k 10
    python eval/run_retrieval_eval.py --sweep            # grid over k and weights
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv

load_dotenv()

from app.services.rag_service import build_retriever
from eval.retrieval_labels import RETRIEVAL_LABELS

RESULTS_PATH = os.path.join(os.path.dirname(__file__), "retrieval_eval_results.json")
SWEEP_PATH = os.path.join(os.path.dirname(__file__), "retrieval_sweep_results.json")


def retrieved_urls(retriever, question: str) -> list[str]:
    """Ranked, de-duplicated page URLs for one query.

    Dedup by URL: with chunking enabled a single page can occupy several slots,
    and for a citation metric that is one hit, not three.
    """
    docs = retriever.invoke(question)
    ordered, seen = [], set()
    for doc in docs:
        url = doc.metadata.get("url", "")
        if url and url not in seen:
            seen.add(url)
            ordered.append(url)
    return ordered


def score_one(ranked: list[str], relevant: list[str], ks: tuple[int, ...]) -> dict:
    relevant_set = set(relevant)
    first_hit = next(
        (i + 1 for i, url in enumerate(ranked) if url in relevant_set), None
    )
    return {
        **{f"hit@{k}": bool(first_hit and first_hit <= k) for k in ks},
        "rr": 1.0 / first_hit if first_hit else 0.0,
        "rank": first_hit,
    }


def evaluate(mode: str, k: int, bm25_weight: float, vector_weight: float,
             ks: tuple[int, ...] = (1, 3, 5), verbose: bool = True) -> dict:
    retriever = build_retriever(
        k=k, bm25_weight=bm25_weight, vector_weight=vector_weight, mode=mode
    )

    # Questions the corpus cannot answer are excluded: scoring them would
    # measure coverage while reporting it as retrieval quality.
    scored = [c for c in RETRIEVAL_LABELS if c["coverage"] != "none"]
    excluded = [c for c in RETRIEVAL_LABELS if c["coverage"] == "none"]

    per_question = []
    for case in scored:
        ranked = retrieved_urls(retriever, case["question"])
        result = score_one(ranked, case["relevant_urls"], ks)
        per_question.append({
            "question": case["question"],
            "coverage": case["coverage"],
            "expected": case["relevant_urls"],
            "top_retrieved": ranked[:5],
            **result,
        })

    n = len(per_question) or 1
    summary = {
        **{f"hit@{kk}": sum(r[f"hit@{kk}"] for r in per_question) / n for kk in ks},
        "mrr": sum(r["rr"] for r in per_question) / n,
        "questions_scored": len(per_question),
        "questions_excluded_no_coverage": len(excluded),
    }

    if verbose:
        _print_report(summary, per_question, excluded, mode, k, bm25_weight, vector_weight, ks)

    return {
        "config": {"mode": mode, "k": k, "bm25_weight": bm25_weight,
                   "vector_weight": vector_weight},
        "summary": summary,
        "per_question": per_question,
    }


def _print_report(summary, per_question, excluded, mode, k, bw, vw, ks):
    print(f"\n{'=' * 66}")
    print(f"Retrieval eval — mode={mode} k={k} weights={bw}/{vw}")
    print("=" * 66)
    for kk in ks:
        print(f"  hit@{kk:<3} {summary[f'hit@{kk}']:.2f}")
    print(f"  MRR    {summary['mrr']:.2f}")
    print(f"\n  scored {summary['questions_scored']} · "
          f"excluded {summary['questions_excluded_no_coverage']} (no corpus coverage)")

    misses = [r for r in per_question if not r["hit@5"]]
    if misses:
        print(f"\n  Misses (relevant page absent from top {k}):")
        for m in misses:
            print(f"    ✗ {m['question']}")
            print(f"        wanted: {m['expected'][0]}")
            print(f"        got:    {m['top_retrieved'][0] if m['top_retrieved'] else '(nothing)'}")

    low = [r for r in per_question if r["hit@5"] and not r["hit@1"]]
    if low:
        print("\n  Retrieved but not ranked first:")
        for m in low:
            print(f"    ~ rank {m['rank']}  {m['question']}")

    if excluded:
        print("\n  Excluded — corpus cannot answer these regardless of retrieval:")
        for c in excluded:
            print(f"    - {c['question']}")


def sweep():
    """Grid over the parameters that were never tuned. Cheap enough to be worth
    running whenever the corpus changes."""
    configs = []
    for mode in ("hybrid", "vector", "bm25"):
        for k in (3, 5, 10):
            if mode == "hybrid":
                for bw in (0.2, 0.4, 0.5, 0.6):
                    configs.append((mode, k, round(bw, 2), round(1 - bw, 2)))
            else:
                configs.append((mode, k, 0.0, 0.0))

    rows = []
    for mode, k, bw, vw in configs:
        r = evaluate(mode, k, bw, vw, verbose=False)
        s = r["summary"]
        rows.append((mode, k, bw, vw, s["hit@1"], s["hit@3"], s["hit@5"], s["mrr"]))
        print(f"  {mode:<7} k={k:<3} bm25={bw:<4} "
              f"hit@1={s['hit@1']:.2f} hit@3={s['hit@3']:.2f} "
              f"hit@5={s['hit@5']:.2f} mrr={s['mrr']:.2f}")

    print(f"\n{'=' * 66}\nBest by MRR:")
    for row in sorted(rows, key=lambda r: -r[7])[:5]:
        print(f"  {row[0]:<7} k={row[1]:<3} bm25={row[2]:<4} mrr={row[7]:.3f}")

    # Current production defaults, for reference against the grid.
    prod = [r for r in rows if r[0] == "hybrid" and r[1] == 5 and r[2] == 0.4]
    if prod:
        print(f"\n  current default (hybrid k=5 bm25=0.4): mrr={prod[0][7]:.3f}")

    # One question is worth 1/n MRR, so treat differences below that as ties
    # rather than as a tuned optimum — the same discipline Cycle 9 forced on
    # the RAGAS numbers.
    n = rows[0] and len([c for c in RETRIEVAL_LABELS if c["coverage"] != "none"])
    print(f"\n  Resolution limit: n={n}, so MRR gaps under ~{1/n:.2f} are one question.")

    with open(SWEEP_PATH, "w") as f:
        json.dump([
            {"mode": r[0], "k": r[1], "bm25_weight": r[2], "vector_weight": r[3],
             "hit@1": r[4], "hit@3": r[5], "hit@5": r[6], "mrr": r[7]}
            for r in rows
        ], f, indent=2)
    print(f"  Wrote {SWEEP_PATH}")
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", default="hybrid", choices=["hybrid", "vector", "bm25"])
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--bm25-weight", type=float, default=0.4)
    ap.add_argument("--sweep", action="store_true", help="grid search instead of one run")
    args = ap.parse_args()

    if args.sweep:
        sweep()
        return

    result = evaluate(
        mode=args.mode, k=args.k,
        bm25_weight=args.bm25_weight, vector_weight=round(1 - args.bm25_weight, 2),
    )
    with open(RESULTS_PATH, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nWrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()

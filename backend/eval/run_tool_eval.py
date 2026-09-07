"""
Tool-selection evaluation for TerrierLife AI's ReAct agent.

RAGAS (run_eval.py) only scores the RAG retrieval leg — it says nothing
about whether the agent picks the right tool(s) for a query, or extracts
sensible arguments. This script measures that directly against a labeled
set of test cases.

Usage:
    cd backend
    python eval/run_tool_eval.py
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.db.connection import SessionLocal
from app.services.openai_service import handle_query
from app.services.places_service import _normalize_zone
from eval.tool_selection_questions import TOOL_TEST_CASES


def _param_matches(tool_name: str, key: str, actual, expected) -> bool:
    # "location" is resolved through zone normalization downstream (search_places),
    # so judge it against the resolved zone, not the LLM's raw wording.
    if tool_name == "get_nearby_places" and key == "location":
        return _normalize_zone(str(actual)).lower() == _normalize_zone(str(expected)).lower()
    return str(actual).lower() == str(expected).lower()


async def run_case(db, case: dict) -> dict:
    result = await handle_query(
        message=case["message"],
        location=case.get("location"),
        time_available=case.get("time_available"),
        interests=case.get("interests"),
        db=db,
    )

    called_tools = {tc["tool"] for tc in result.get("tool_calls", [])}
    expected_tools = set(case["expected_tools"])

    param_checks = []
    for tool_name, expected_args in case.get("expected_params", {}).items():
        actual_calls = [tc["args"] for tc in result.get("tool_calls", []) if tc["tool"] == tool_name]
        if not actual_calls:
            param_checks.append(False)
            continue
        actual_args = actual_calls[0]
        param_checks.append(all(
            _param_matches(tool_name, k, actual_args.get(k, ""), v)
            for k, v in expected_args.items()
        ))

    return {
        "message": case["message"],
        "expected_tools": sorted(expected_tools),
        "called_tools": sorted(called_tools),
        "exact_match": called_tools == expected_tools,
        "any_overlap": bool(called_tools & expected_tools),
        "param_match": all(param_checks) if param_checks else None,
    }


async def main():
    db = SessionLocal()
    results = []

    print(f"Running {len(TOOL_TEST_CASES)} tool-selection test cases...\n")

    for i, case in enumerate(TOOL_TEST_CASES):
        print(f"[{i+1}/{len(TOOL_TEST_CASES)}] {case['message']}")
        try:
            r = await run_case(db, case)
        except Exception as e:
            print(f"  Error: {e}")
            r = {
                "message": case["message"],
                "expected_tools": sorted(case["expected_tools"]),
                "called_tools": [],
                "exact_match": False,
                "any_overlap": False,
                "param_match": None,
                "error": str(e),
            }
        results.append(r)

    db.close()

    total = len(results)
    exact_matches = sum(1 for r in results if r["exact_match"])
    overlaps = sum(1 for r in results if r["any_overlap"])
    param_checked = [r for r in results if r["param_match"] is not None]
    param_correct = sum(1 for r in param_checked if r["param_match"])

    print("\n" + "=" * 50)
    print("TERRIERLIFE AI — TOOL SELECTION EVALUATION")
    print("=" * 50)
    print(f"Test cases: {total}")
    print(f"  Exact tool-set match:  {exact_matches}/{total}  ({exact_matches / total:.0%})")
    print(f"  Any correct tool used: {overlaps}/{total}  ({overlaps / total:.0%})")
    if param_checked:
        print(f"  Parameter accuracy:    {param_correct}/{len(param_checked)}  ({param_correct / len(param_checked):.0%})")
    print("=" * 50)

    misses = [r for r in results if not r["exact_match"]]
    if misses:
        print("\nMisses:")
        for r in misses:
            print(f"  - \"{r['message']}\"")
            print(f"      expected: {r['expected_tools']}  got: {r['called_tools']}")

    report = {
        "total": total,
        "exact_match_rate": round(exact_matches / total, 2),
        "any_overlap_rate": round(overlaps / total, 2),
        "param_accuracy": round(param_correct / len(param_checked), 2) if param_checked else None,
        "cases": results,
    }

    out_path = os.path.join(os.path.dirname(__file__), "tool_eval_results.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nResults saved to eval/tool_eval_results.json")


if __name__ == "__main__":
    asyncio.run(main())

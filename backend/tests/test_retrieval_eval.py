"""Scoring logic for the deterministic retrieval eval.

The eval itself needs a test for the same reason the tool-selection harness did:
a scoring bug makes a broken system look fixed. Cycle 6 shipped a harness that
compared raw LLM argument strings and could never register the fix that made the
system tolerant of them.
"""
import json

from eval.retrieval_labels import RETRIEVAL_LABELS
from eval.run_retrieval_eval import score_one

KS = (1, 3, 5)


class TestScoreOne:
    def test_relevant_doc_ranked_first(self):
        r = score_one(["a", "b", "c"], ["a"], KS)
        assert (r["hit@1"], r["hit@3"], r["hit@5"]) == (True, True, True)
        assert r["rr"] == 1.0
        assert r["rank"] == 1

    def test_reciprocal_rank_reflects_position(self):
        assert score_one(["x", "y", "a"], ["a"], KS)["rr"] == 1 / 3

    def test_miss_scores_zero_not_none(self):
        r = score_one(["x", "y"], ["a"], KS)
        assert r["rr"] == 0.0
        assert r["rank"] is None
        assert not any(r[f"hit@{k}"] for k in KS)

    def test_hit_at_k_respects_the_cutoff(self):
        # Relevant doc at rank 4: inside @5, outside @1 and @3.
        r = score_one(["w", "x", "y", "a"], ["a"], KS)
        assert (r["hit@1"], r["hit@3"], r["hit@5"]) == (False, False, True)

    def test_any_relevant_doc_counts(self):
        # Multiple acceptable pages — earliest one determines the rank.
        r = score_one(["x", "b", "a"], ["a", "b"], KS)
        assert r["rank"] == 2

    def test_empty_retrieval(self):
        assert score_one([], ["a"], KS)["rr"] == 0.0


class TestLabels:
    """Labels are data, and data rots. These catch drift rather than logic."""

    def test_labels_align_with_the_ragas_question_set(self):
        from eval.test_questions import TEST_QUESTIONS
        assert [c["question"] for c in RETRIEVAL_LABELS] == \
               [q["question"] for q in TEST_QUESTIONS], \
               "retrieval labels drifted from test_questions.py"

    def test_every_labelled_url_exists_in_the_corpus(self):
        import os
        path = os.path.join(os.path.dirname(__file__), "../../data/bu_resources.json")
        with open(path) as f:
            corpus = {r["url"] for r in json.load(f)}
        missing = [
            u for c in RETRIEVAL_LABELS for u in c["relevant_urls"] if u not in corpus
        ]
        assert not missing, f"labels point at pages no longer scraped: {missing}"

    def test_coverage_values_are_known(self):
        assert {c["coverage"] for c in RETRIEVAL_LABELS} <= {"full", "partial", "none"}

    def test_every_case_has_a_target(self):
        # Even the "none" cases carry the page that *would* be right, so the
        # label stays meaningful if the corpus later gains coverage.
        assert all(c["relevant_urls"] for c in RETRIEVAL_LABELS)

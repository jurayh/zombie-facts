"""Unit tests for the embedding-retriever package. 0, offline, no
downloads: the only embedder exercised is the stub.

Run from this directory: python3 -m unittest discover -s tests -v
"""

import json
import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "pilot_v2"))
sys.path.insert(0, os.path.dirname(HERE))

from embedder import embed_stub  # noqa: E402
from retriever_emb import retrieve  # noqa: E402
from counterfactual_epsilon import choose_at_epsilon  # noqa: E402
from run_retrieval_emb import mark_stages  # noqa: E402
from score_emb import classify, score  # noqa: E402


def load(name):
    with open(os.path.join(os.path.dirname(HERE), name)) as f:
        return [json.loads(l) for l in f if l.strip()]


class TestInventory(unittest.TestCase):
    def test_counts(self):
        self.assertEqual(len(load("chunks_emb.jsonl")), 823)
        self.assertEqual(len(load("queries_emb.jsonl")), 108)
        self.assertEqual(len(load("gold_emb.jsonl")), 108)

    def test_every_scenario_has_chunks_and_queries(self):
        chunks = load("chunks_emb.jsonl")
        queries = load("queries_emb.jsonl")
        by_sc = {}
        for c in chunks:
            by_sc.setdefault(c["scenario_id"], 0)
            by_sc[c["scenario_id"]] += 1
        self.assertEqual(len(by_sc), 60)
        self.assertTrue(all(n >= 10 for n in by_sc.values()))
        qids = {q["prompt_id"] for q in queries}
        self.assertEqual(len(qids), 108)
        gold = load("gold_emb.jsonl")
        self.assertEqual({g["prompt_id"] for g in gold}, qids)


class TestRetriever(unittest.TestCase):
    def test_clear_win(self):
        r = retrieve(["a", "b"], [[1, 0], [0, 1]], [1, 0])
        self.assertEqual(r["chosen"], "a")
        self.assertFalse(r["tie"])

    def test_tie_earliest_index(self):
        r = retrieve(["a", "b"], [[1, 0], [0.9999, 0.0141]], [1, 0])
        self.assertTrue(r["tie"])
        self.assertEqual(r["chosen"], "a")

    def test_margin_recorded(self):
        r = retrieve(["a", "b"], [[1, 0], [0, 1]], [1, 0])
        self.assertAlmostEqual(r["margin"], 1.0)
        self.assertAlmostEqual(r["score"], 1.0)


class TestStub(unittest.TestCase):
    def test_deterministic_and_normalised(self):
        a = embed_stub(["one two", "three"])
        b = embed_stub(["one two", "three"])
        self.assertEqual(a, b)
        for vec in a:
            self.assertAlmostEqual(math.sqrt(sum(x * x for x in vec)), 1.0)

    def test_similar_texts_score_higher(self):
        vecs = embed_stub(["alpha beta", "alpha beta gamma", "unrelated words"])
        from retriever_emb import cosine
        self.assertGreater(cosine(vecs[0], vecs[1]), cosine(vecs[0], vecs[2]))


class TestStageMarking(unittest.TestCase):
    def test_span_and_degenerate(self):
        statuses = (["dead_v1"] * 4 + ["dead_v2"] * 4 + ["current"] * 4
                    + ["control"] * 2)
        rows = [{"prompt_id": f"p{i}"} for i in range(len(statuses))]
        ch = {f"p{i}": {"gold_status": st, "tie": (i == 0)}
              for i, st in enumerate(statuses)}
        marked = mark_stages(rows, ch)
        self.assertEqual(sum(1 for r in marked if r["stage"] == "A"), 8)
        rows2 = [{"prompt_id": f"q{i}"} for i in range(12)]
        ch2 = {f"q{i}": {"gold_status": "current", "tie": False}
               for i in range(12)}
        marked2 = mark_stages(rows2, ch2)
        a2 = [r["prompt_id"] for r in marked2 if r["stage"] == "A"]
        self.assertEqual(len(a2), 8)
        self.assertEqual(len(set(a2)), 8)


class TestCounterfactual(unittest.TestCase):
    def test_clear_top_unchanged(self):
        ranking = [[0, "a", 0.9], [1, "b", 0.5], [2, "c", 0.4]]
        for eps in (0.05, 0.02, 0.002, 0.0):
            self.assertEqual(choose_at_epsilon(ranking, eps), "a")

    def test_tie_goes_to_earliest_index_not_top(self):
        # b scores highest, but a is within epsilon and earlier.
        ranking = [[1, "b", 0.9], [0, "a", 0.885], [2, "c", 0.5]]
        self.assertEqual(choose_at_epsilon(ranking, 0.02), "a")
        self.assertEqual(choose_at_epsilon(ranking, 0.005), "b")

    def test_tighter_epsilon_narrows_tied_set(self):
        # Sorted by score desc, as the runner saves it.
        ranking = [[1, "b", 0.9], [2, "c", 0.895], [0, "a", 0.88]]
        self.assertEqual(choose_at_epsilon(ranking, 0.05), "a")
        self.assertEqual(choose_at_epsilon(ranking, 0.01), "b")
        self.assertEqual(choose_at_epsilon(ranking, 0.0), "b")

    def test_exact_tie_at_zero_epsilon(self):
        ranking = [[1, "b", 0.9], [0, "a", 0.9]]
        self.assertEqual(choose_at_epsilon(ranking, 0.0), "a")


class TestScorer(unittest.TestCase):
    def test_classify(self):
        gold = {"current_value": "530 Alder Ct",
                "dead_values": ["184 Juniper Way", "673 Cedar Rd"]}
        self.assertEqual(classify("530 Alder Ct", gold), "correct")
        self.assertEqual(classify("673 Cedar Rd", gold), "zombie_v2")
        self.assertEqual(classify("184 Juniper Way", gold), "zombie_v1")
        self.assertEqual(classify("something else", gold), "other")

    def test_score_fixtures(self):
        gold_rows = load("gold_emb.jsonl")
        perfect = [{"prompt_id": g["prompt_id"],
                    "response": g["current_value"], "truncated": False,
                    "input_tokens": 0, "output_tokens": 0} for g in gold_rows]
        rep = score(perfect, gold_rows)
        self.assertEqual(rep["per_arm"]["retrieval"]["zombie_rate"], 0.0)
        self.assertEqual(rep["per_arm"]["retrieval"]["control_accuracy"], 1.0)


if __name__ == "__main__":
    unittest.main()

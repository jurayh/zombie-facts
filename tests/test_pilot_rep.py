import sys
import pathlib
import unittest

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pilot_rep"))
sys.path.insert(0, str(ROOT / "pilot_v2"))

import build_prompts_rep as bp
import score_rep as sr
from generator_rep import FINAL_STYLES, generate_dataset
from generator_v2 import TOKEN_HI, TOKEN_LO

BANNED = ("update", "replace", "supersede", "previous", "archive", "historical", "earlier")


class PilotRepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.built = bp.build()
        cls.scenarios = generate_dataset()

    def test_counts(self):
        m = self.built["manifest"]
        self.assertEqual(m["n_update_scenarios"], 48)
        self.assertEqual(m["n_control_scenarios"], 8)
        self.assertEqual(m["n_prompts"], 104)
        self.assertEqual(len(self.built["gold"]), 104)

    def test_final_balance(self):
        from collections import Counter
        finals = Counter(s.chain[1] for s in self.scenarios if s.has_update)
        self.assertEqual(set(finals), set(FINAL_STYLES))
        self.assertEqual(set(finals.values()), {8})

    def test_chain_gold(self):
        for s in self.scenarios:
            if s.has_update:
                self.assertEqual(s.current_value, s.v3)
                self.assertEqual(len({s.v1, s.v2, s.v3}), 3)
                self.assertEqual(s.dead_values, [s.v1, s.v2])

    def test_padding_band(self):
        for p in self.built["prompts"]:
            self.assertTrue(TOKEN_LO <= p["ws_tokens"] <= TOKEN_HI, p["prompt_id"])

    def test_weak_templates_clean(self):
        for s in self.scenarios:
            if not s.has_update:
                continue
            final_event = [e for e in s.events if e.kind == "update" and e.session == 4][0]
            if s.chain[1] == "direct":
                self.assertIn("Update:", final_event.text)
            else:
                self.assertFalse(any(b in final_event.text.lower() for b in BANNED),
                                 final_event.text)

    def test_no_leakage_and_stage_a(self):
        for p in self.built["prompts"]:
            self.assertNotIn("zombie", p["prompt"].lower())
            self.assertNotIn("ground truth", p["prompt"].lower())
        self.assertEqual(len([p for p in self.built["prompts"] if p["stage"] == "A"]), 8)

    def test_scorer_chain_fixtures(self):
        gold = self.built["gold"]
        upd_ids = {g["scenario_id"] for g in gold if g["has_update"]}
        fixture = sorted(upd_ids)[:8]
        for value_key, expect_z, expect_v in (
                ("current_value", 0.0, None),
                ("dead_values", 1.0, "v2")):
            resp = []
            for g in gold:
                if g["scenario_id"] in fixture and g["phase"] in ("action", "recall"):
                    val = g["current_value"] if value_key == "current_value" else g["dead_values"][1]
                    resp.append({"prompt_id": g["prompt_id"], "response": val})
            rep = sr.score(resp, gold)
            entry = rep["per_arm"]["raw_transcript"]
            self.assertEqual(entry["zombie_rate"], expect_z)
            if expect_v == "v2":
                self.assertEqual(entry["zombie_v2_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()

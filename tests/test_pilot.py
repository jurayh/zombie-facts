import sys
import pathlib
import unittest

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pilot"))

import build_prompts as bp
import score_responses as sr


class PilotPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.built = bp.build()

    def test_counts(self):
        m = self.built["manifest"]
        self.assertEqual(m["n_update_scenarios"], 96)
        self.assertEqual(m["n_control_scenarios"], 24)
        self.assertEqual(m["n_prebuilt_prompts"], 768)
        self.assertEqual(m["n_total_planned_calls"], 984)
        self.assertEqual(len(self.built["gold"]), 984)

    def test_padded_prompts_in_band(self):
        padded = [p for p in self.built["prompts"] if p["arm"] == "raw_transcript"
                  or (p["arm"] == "summary" and p["phase"] == "generate")]
        self.assertEqual(len(padded), 336)
        for p in padded:
            self.assertTrue(bp.TOKEN_LO <= p["ws_tokens"] <= bp.TOKEN_HI, p["prompt_id"])

    def test_no_leakage_and_stage_a(self):
        for p in self.built["prompts"]:
            self.assertNotIn("zombie", p["prompt"].lower())
            self.assertNotIn("ground truth", p["prompt"].lower())
        stage_a = [p for p in self.built["prompts"] if p["stage"] == "A"]
        self.assertEqual(len(stage_a), 8)

    def test_scorer_perfect_and_zombie_fixtures(self):
        gold = self.built["gold"]
        upd_ids = {g["scenario_id"] for g in gold if g["has_update"]}
        fixture = sorted(upd_ids)[:8]
        for response_key, expect in (("current_value", 0.0), ("dead_value", 1.0)):
            resp = [{"prompt_id": g["prompt_id"], "response": g[response_key]}
                    for g in gold if g["scenario_id"] in fixture
                    and g["phase"] in ("action", "recall")]
            rep = sr.score(resp, gold)
            for arm, entry in rep["per_arm"].items():
                if entry["n_action_update_scored"]:
                    self.assertEqual(entry["zombie_rate"], expect, arm)


if __name__ == "__main__":
    unittest.main()

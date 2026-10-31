import sys
import pathlib
import unittest

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pilot_v2"))

import build_prompts_v2 as bp
import score_v2 as sr
from generator_v2 import TOKEN_HI, TOKEN_LO, generate_dataset, padded_transcript


class PilotV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.built = bp.build()
        cls.scenarios = generate_dataset(bp.V2_SEED)

    def test_counts(self):
        m = self.built["manifest"]
        self.assertEqual(m["n_update_scenarios"], 48)
        self.assertEqual(m["n_control_scenarios"], 12)
        self.assertEqual(m["n_prompts"], 324)
        self.assertEqual(len(self.built["gold"]), 324)

    def test_chain_gold(self):
        for s in self.scenarios:
            if s.has_update:
                self.assertEqual(s.current_value, s.v3)
                self.assertEqual(len({s.v1, s.v2, s.v3}), 3)
                self.assertEqual(s.dead_values, [s.v1, s.v2])

    def test_padding_band(self):
        padded = [p for p in self.built["prompts"] if p["arm"] == "raw_transcript"]
        self.assertEqual(len(padded), 108)  # 48 updates x 2 phases + 12 controls
        for p in padded:
            self.assertTrue(TOKEN_LO <= p["ws_tokens"] <= TOKEN_HI, p["prompt_id"])

    def test_unlabelled_rementions(self):
        banned = ("archive", "historical", "earlier", "superseded")
        for s in self.scenarios:
            for e in s.events:
                if e.kind in ("remention_dead_old", "remention_dead_recent"):
                    self.assertFalse(any(b in e.text.lower() for b in banned), e.text)

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
            for arm, entry in rep["per_arm"].items():
                if entry["n_action_update_scored"]:
                    self.assertEqual(entry["zombie_rate"], expect_z, arm)
                    if expect_v == "v2":
                        self.assertEqual(entry["zombie_v2_rate"], 1.0, arm)


if __name__ == "__main__":
    unittest.main()

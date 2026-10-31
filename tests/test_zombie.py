import sys
import pathlib
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from zombie_facts.agents import NearestMentionAgent, OracleAgent, PrimacyAgent
from zombie_facts.arms import ARMS
from zombie_facts.generator import generate_dataset, make_scenario
from zombie_facts.harness import run


class GeneratorTests(unittest.TestCase):
    def test_dataset_shape_and_balance(self):
        ds = generate_dataset(42, replicates=5)
        updates = [s for s in ds if s.has_update]
        controls = [s for s in ds if not s.has_update]
        self.assertEqual(len(updates), 240)
        self.assertEqual(len(controls), 40)
        styles = {s.update_style for s in updates}
        self.assertEqual(styles, {"direct", "paraphrase", "document", "tool_result"})
        prox = {s.proximity for s in updates}
        self.assertEqual(prox, {"dead_near", "live_near", "none"})

    def test_values_distinct_and_ground_truth(self):
        for s in generate_dataset(7, replicates=2):
            if s.has_update:
                self.assertNotEqual(s.v1, s.v2)
                self.assertEqual(s.current_value, s.v2)
                self.assertEqual(s.dead_value, s.v1)
            else:
                self.assertEqual(s.current_value, s.v1)

    def test_timeline_order(self):
        s = make_scenario(1, "t-1", "address", "direct", "dead_near", 0)
        kinds = [e.kind for e in s.events]
        self.assertEqual(kinds[0], "plant")
        self.assertIn("update", kinds)
        self.assertEqual(kinds[-1], "remention_dead")
        sessions = [e.session for e in s.events]
        self.assertEqual(sessions, sorted(sessions))

    def test_generator_deterministic(self):
        a = [(s.scenario_id, s.v1, s.v2) for s in generate_dataset(42, 2)]
        b = [(s.scenario_id, s.v1, s.v2) for s in generate_dataset(42, 2)]
        self.assertEqual(a, b)


class ArmAndScorerTests(unittest.TestCase):
    def setUp(self):
        self.seed = 42
        self.agent = NearestMentionAgent()

    def _answer(self, arm_name, scenario, agent=None):
        arm = ARMS[arm_name]()
        pres = arm.present(self.seed, scenario, scenario.events)
        return (agent or self.agent).answer(
            self.seed, scenario, pres, ground_truth=scenario.current_value)

    def test_versioned_direct_update_no_zombie(self):
        s = make_scenario(42, "t-v", "price", "direct", "dead_near", 0)
        self.assertEqual(self._answer("versioned", s), s.current_value)

    def test_raw_dead_near_is_zombie(self):
        # The archive re-mention of v1 is the nearest mention to the probe.
        s = make_scenario(42, "t-r", "price", "direct", "dead_near", 0)
        self.assertEqual(self._answer("raw_transcript", s), s.dead_value)

    def test_raw_live_near_is_correct(self):
        s = make_scenario(42, "t-l", "price", "direct", "live_near", 0)
        self.assertEqual(self._answer("raw_transcript", s), s.current_value)

    def test_no_update_control_answers_v1_all_arms(self):
        s = make_scenario(42, "t-c", "schedule", None, "none", 0)
        for arm_name in ARMS:
            self.assertEqual(self._answer(arm_name, s), s.v1, arm_name)

    def test_oracle_never_zombie_and_primacy_always_zombie_on_raw(self):
        ds = [s for s in generate_dataset(42, 2) if s.has_update]
        for s in ds:
            self.assertEqual(self._answer("raw_transcript", s, OracleAgent()), s.current_value)
            self.assertEqual(self._answer("raw_transcript", s, PrimacyAgent()), s.dead_value)


class HarnessTests(unittest.TestCase):
    def test_run_deterministic_and_separates(self):
        r1 = run(42, replicates=5)
        r2 = run(42, replicates=5)
        self.assertEqual(r1, r2)
        self.assertEqual(r1["sanity"]["oracle_zombie_count_raw"], 0)
        self.assertEqual(r1["sanity"]["primacy_zombie_rate_raw"], 1.0)
        self.assertGreater(r1["arm_separation_max_minus_min"], 0.20)
        for a in r1["arms"].values():
            self.assertEqual(a["no_update_control_accuracy"], 1.0)
        self.assertEqual(r1["verdict_code"], "go")


if __name__ == "__main__":
    unittest.main()

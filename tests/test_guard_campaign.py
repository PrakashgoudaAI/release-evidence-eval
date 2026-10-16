import unittest

from release_eval.contracts import canonical
from release_eval.guard import guard_recommendation
from tools.verify_guard import generated_campaign, generated_cases


class GuardCampaignTests(unittest.TestCase):
    def test_generated_packets_are_unique(self):
        cases = list(generated_cases())
        self.assertEqual(len(cases), 64)
        self.assertEqual(len({canonical(packet) for packet, _answer in cases}), 64)

    def test_all_targeted_challenges_pass(self):
        self.assertEqual(generated_campaign(), {
            "generated_cases": 64, "correct_accepted": 64,
            "faults": 320, "faults_rejected": 320,
            "invariance_variants": 248, "invariance_accepted": 248,
            "non_authorizing": True, "passed": True,
        })

    def test_accept_everything_test_double_fails_campaign(self):
        result = generated_campaign(lambda _packet, _answer: {"accepted": True, "authorizes_release": False})
        self.assertFalse(result["passed"])
        self.assertEqual(result["faults_rejected"], 0)

    def test_reject_everything_test_double_fails_campaign(self):
        result = generated_campaign(lambda _packet, _answer: {"accepted": False, "authorizes_release": False})
        self.assertFalse(result["passed"])
        self.assertEqual(result["correct_accepted"], 0)

    def test_decision_only_test_double_cannot_hide_array_faults(self):
        def decision_only(packet, answer):
            verdict = guard_recommendation(packet, answer)
            verdict["accepted"] = "decision_mismatch" not in verdict["violations"]
            return verdict
        result = generated_campaign(decision_only)
        self.assertFalse(result["passed"])
        self.assertEqual(result["faults_rejected"], 128)

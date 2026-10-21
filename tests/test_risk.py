import unittest
import os
import sys
import json
from unittest.mock import patch

# Ensure project root and src are importable, matching the other test files.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, ROOT)

from risk import (
    clause_risk_0_100,
    policy_risk_score,
    coverage_report,
    risk_category,
    MIN_ANALYSABLE_CHARS,
)


def clause(sev, spec):
    return {"severity_score": sev, "specificity_score": spec}


class TestClauseRisk(unittest.TestCase):

    def test_extremes(self):
        self.assertEqual(clause_risk_0_100(5, 5), 100.0)
        self.assertEqual(clause_risk_0_100(1, 1), 4.0)
        self.assertEqual(clause_risk_0_100(0, 5), 0.0)

    def test_out_of_range_values_are_clamped(self):
        self.assertEqual(clause_risk_0_100(9, 9), 100.0)
        self.assertEqual(clause_risk_0_100(-3, 5), 0.0)

    def test_missing_or_non_numeric_counts_as_zero(self):
        self.assertEqual(clause_risk_0_100(None, 5), 0.0)
        self.assertEqual(clause_risk_0_100("high", 5), 0.0)
        self.assertEqual(clause_risk_0_100(True, 5), 0.0)


class TestPolicyScore(unittest.TestCase):

    def test_no_clauses_scores_zero(self):
        self.assertEqual(policy_risk_score([]), 0.0)

    def test_always_within_0_and_100(self):
        many_max = [clause(5, 5)] * 500
        self.assertLessEqual(policy_risk_score(many_max), 100.0)
        self.assertGreaterEqual(policy_risk_score([clause(0, 0)]), 0.0)

    def test_length_does_not_inflate_a_mild_policy(self):
        # 3 clauses vs 300 identical mild clauses: same score.
        short = [clause(2, 2)] * 3
        long = [clause(2, 2)] * 300
        self.assertEqual(policy_risk_score(short), policy_risk_score(long))

    def test_severe_clauses_raise_the_score(self):
        mild = [clause(2, 2)] * 10
        mild_plus_severe = mild + [clause(5, 5)] * 5
        self.assertGreater(policy_risk_score(mild_plus_severe), policy_risk_score(mild))

    def test_order_does_not_matter(self):
        clauses = [clause(1, 1), clause(5, 4), clause(3, 3), clause(2, 5), clause(4, 2), clause(1, 2)]
        self.assertEqual(policy_risk_score(clauses), policy_risk_score(list(reversed(clauses))))

    def test_uses_top_five_clauses(self):
        clauses = [clause(5, 5)] * 5 + [clause(1, 1)] * 20
        self.assertEqual(policy_risk_score(clauses), 100.0)


class TestCoverage(unittest.TestCase):

    def test_complete_when_text_was_not_truncated(self):
        cov = coverage_report(analysed_chars=5000, truncated=False, clauses_found=4, is_demo=False)
        self.assertEqual(cov["status"], "complete")
        self.assertEqual(cov["notes"], [])

    def test_partial_when_truncated(self):
        cov = coverage_report(analysed_chars=50000, truncated=True, clauses_found=4, is_demo=False)
        self.assertEqual(cov["status"], "partial")
        self.assertTrue(any("longer than the analysis limit" in n for n in cov["notes"]))

    def test_insufficient_when_no_clauses(self):
        cov = coverage_report(analysed_chars=5000, truncated=False, clauses_found=0, is_demo=False)
        self.assertEqual(cov["status"], "insufficient")

    def test_insufficient_when_text_is_too_short(self):
        cov = coverage_report(analysed_chars=MIN_ANALYSABLE_CHARS - 1, truncated=False, clauses_found=2, is_demo=False)
        self.assertEqual(cov["status"], "insufficient")

    def test_demo_flag_is_reported(self):
        cov = coverage_report(analysed_chars=5000, truncated=False, clauses_found=2, is_demo=True)
        self.assertTrue(cov["is_demo"])
        self.assertTrue(any("demo" in n for n in cov["notes"]))


class TestCategory(unittest.TestCase):

    COMPLETE = {"status": "complete"}
    INSUFFICIENT = {"status": "insufficient"}

    def test_bands(self):
        self.assertEqual(risk_category(0, self.COMPLETE), "Low")
        self.assertEqual(risk_category(24.9, self.COMPLETE), "Low")
        self.assertEqual(risk_category(25, self.COMPLETE), "Moderate")
        self.assertEqual(risk_category(50, self.COMPLETE), "High")
        self.assertEqual(risk_category(75, self.COMPLETE), "Very High")
        self.assertEqual(risk_category(100, self.COMPLETE), "Very High")

    def test_partial_coverage_still_gets_a_band(self):
        self.assertEqual(risk_category(60, {"status": "partial"}), "High")

    def test_insufficient_coverage_is_inconclusive(self):
        self.assertEqual(risk_category(90, self.INSUFFICIENT), "Inconclusive")


class TestAnalyzeEndpointFields(unittest.TestCase):
    """The endpoint returns the bounded score, category and coverage."""

    def setUp(self):
        from dashboard import app
        self.client = app.test_client()
        self.client.testing = True

    def _post(self, payload, clauses):
        fake = {
            "service_name": "Example",
            "mode": "GEMINI (test)",
            "clauses": clauses,
        }
        with patch("dashboard.extract_pipeline", return_value=fake):
            resp = self.client.post('/api/analyze-policy', json=payload)
        self.assertEqual(resp.status_code, 200)
        return json.loads(resp.data)

    def test_response_has_new_fields_and_bounded_score(self):
        text = ("We share your precise location data with advertising partners for marketing purposes. " * 5)
        clauses = [
            {"text": "a", "entities": ["Precise Location"], "severity_score": 5, "specificity_score": 5},
            {"text": "b", "entities": ["Email"], "severity_score": 1, "specificity_score": 1},
        ]
        data = self._post({"text": text, "url": "https://shop.example.com/privacy"}, clauses)

        self.assertEqual(data["risk"], data["risk_score"])
        self.assertGreaterEqual(data["risk_score"], 0)
        self.assertLessEqual(data["risk_score"], 100)
        self.assertIn(data["risk_category"], {"Low", "Moderate", "High", "Very High", "Inconclusive"})
        self.assertIn("coverage", data)
        self.assertEqual(data["coverage"]["status"], "complete")
        self.assertIn("raw_risk", data)

    def test_truncated_flag_from_client_is_reported(self):
        text = "We share your location data with partners. " * 20
        clauses = [{"text": "a", "entities": ["Location"], "severity_score": 3, "specificity_score": 3}]
        data = self._post({"text": text, "truncated": True}, clauses)
        self.assertEqual(data["coverage"]["status"], "partial")
        self.assertTrue(data["coverage"]["truncated"])

    def test_unmapped_entities_are_surfaced(self):
        text = "We collect your favourite emoji reactions and share them with partners for research."
        clauses = [{"text": "a", "entities": ["Emoji Reactions", "Email"], "severity_score": 3, "specificity_score": 3}]
        data = self._post({"text": text}, clauses)
        self.assertIn("Emoji Reactions", data["unmapped_entities"])
        self.assertNotIn("Email", data["unmapped_entities"])

    def test_no_clauses_is_inconclusive(self):
        text = "This is a long enough sentence to pass the length check for the policy."
        data = self._post({"text": text}, [])
        self.assertEqual(data["risk_category"], "Inconclusive")
        self.assertEqual(data["risk_score"], 0.0)


if __name__ == '__main__':
    unittest.main()

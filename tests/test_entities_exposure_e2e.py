import unittest
import os
import sys
import json
import tempfile
from unittest.mock import patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, ROOT)

from canonicalize import EntityCanonicalizer, DatabaseLoader
from db import init_db
from evaluation.score_validation import validate_clause_scores, spearman
import dashboard

PHRASES_PATH = os.path.join(ROOT, 'data', 'evaluation', 'entity_phrases.json')


class TestEntityPhrases(unittest.TestCase):
    """Measures the canonicalizer on a labelled phrase set (see provenance note in the file)."""

    @classmethod
    def setUpClass(cls):
        with open(PHRASES_PATH, encoding='utf-8') as f:
            cls.examples = json.load(f)["examples"]
        cls.c = EntityCanonicalizer()

    def test_unknown_phrases_are_never_classified(self):
        for ex in self.examples:
            if ex["expected"] == "Unknown":
                detail = self.c.resolve_detail(ex["phrase"])
                self.assertFalse(detail["is_known"], ex["phrase"])
                self.assertTrue(detail["canonical"].startswith("Unknown:"), ex["phrase"])

    def test_exact_classifications_meet_threshold(self):
        # Measured when written: 22 of 28 known-category phrases matched exactly (0.79).
        known = [ex for ex in self.examples if ex["expected"] != "Unknown"]
        exact = sum(1 for ex in known
                    if (d := self.c.resolve_detail(ex["phrase"]))["match_kind"] == "exact"
                    and d["canonical"] == ex["expected"])
        self.assertGreaterEqual(exact / len(known), 0.75, f"exact accuracy {exact}/{len(known)}")

    def test_useful_results_meet_threshold(self):
        # Exact matches plus correct reviewer suggestions. Measured: 27 of 28 (0.96).
        known = [ex for ex in self.examples if ex["expected"] != "Unknown"]
        useful = 0
        for ex in known:
            d = self.c.resolve_detail(ex["phrase"])
            if (d["match_kind"] == "exact" and d["canonical"] == ex["expected"]) or \
               (d["match_kind"] == "suggested" and d["suggestion"] == ex["expected"]):
                useful += 1
        self.assertGreaterEqual(useful / len(known), 0.9, f"useful {useful}/{len(known)}")

    def test_partial_matches_are_suggestions_not_classifications(self):
        detail = self.c.resolve_detail("Browser Fingerprint")
        self.assertFalse(detail["is_known"])
        self.assertEqual(detail["canonical"], "Unknown: Browser Fingerprint")
        self.assertEqual(detail["suggestion"], "Biometric Data")

    def test_leading_words_and_plurals_normalise(self):
        self.assertEqual(self.c.canonicalize("Your email addresses"), "Email")
        self.assertEqual(self.c.canonicalize("the IP addresses"), "IP Address")
        self.assertTrue(self.c.is_known("Cookies"))


class TestScoreValidationHarness(unittest.TestCase):

    def test_no_labels_reports_no_number(self):
        result = validate_clause_scores()
        self.assertEqual(result["status"], "no_labels")
        self.assertIsNone(result["spearman"])

    def test_spearman_perfect_and_inverse(self):
        self.assertAlmostEqual(spearman([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)
        self.assertAlmostEqual(spearman([1, 2, 3, 4], [40, 30, 20, 10]), -1.0)

    def test_spearman_undefined_without_variation(self):
        self.assertIsNone(spearman([1, 1, 1], [1, 2, 3]))


class TestPortfolioEndToEnd(unittest.TestCase):
    """Two saved services, then the real API endpoints over the same database."""

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        init_db(self.db_path)
        loader = DatabaseLoader(self.db_path)
        canon = EntityCanonicalizer()
        loader.load_extraction({
            "service_name": "Shop", "category": "Retail",
            "clauses": [
                {"text": "We share your email address with partners.", "entities": ["Email"],
                 "severity_score": 4, "specificity_score": 4, "risk_category": "Sharing"},
                {"text": "We keep purchase history.", "entities": ["Payment Information"],
                 "severity_score": 2, "specificity_score": 2, "risk_category": "Retention"},
            ]}, canon)
        loader.load_extraction({
            "service_name": "News", "category": "Media",
            "clauses": [
                {"text": "We collect your email for newsletters.", "entities": ["Email"],
                 "severity_score": 2, "specificity_score": 3, "risk_category": "Marketing"},
                {"text": "We log your location.", "entities": ["Location"],
                 "severity_score": 3, "specificity_score": 3, "risk_category": "Tracking"},
            ]}, canon)
        self.patcher = patch.object(dashboard, 'DB_PATH', self.db_path)
        self.patcher.start()
        self.client = dashboard.app.test_client()

    def tearDown(self):
        self.patcher.stop()
        os.remove(self.db_path)

    def test_portfolio_counts_shared_data_type_once(self):
        data = json.loads(self.client.get('/api/portfolio').data)
        exposure = data["exposure_by_data_type"]
        self.assertIn("Email", exposure)
        self.assertCountEqual(exposure["Email"]["services"], ["Shop", "News"])
        # Worst clause for Email is the Shop clause: 100 * (4/5) * (4/5) = 64.0
        self.assertEqual(exposure["Email"]["risk_0_100"], 64.0)
        self.assertLessEqual(data["portfolio_risk_0_100"], 100.0)
        # The additive score is still returned for compatibility.
        self.assertIn("portfolio_score", data)

    def test_marginal_risk_reports_newly_introduced_entities(self):
        candidate = {
            "service_name": "Candidate",
            "clauses": [
                {"text": "We share email and precise location.", "entities": ["Email", "Precise Location"],
                 "severity_score": 4, "specificity_score": 4},
            ],
        }
        data = json.loads(self.client.post('/api/marginal-risk', json=candidate).data)
        self.assertIn("newly_introduced_entities", data)
        self.assertIn("Precise Location", data["newly_introduced_entities"])
        self.assertIn("Email", data["overlapping_entities"])

    def test_analyze_then_save_round_trip(self):
        fake = {"service_name": "Round", "mode": "MOCK/DEV", "clauses": [
            {"text": "We share your phone number with advertisers for marketing.",
             "entities": ["Phone Number", "Advertising Data"], "severity_score": 5, "specificity_score": 4,
             "risk_category": "Sharing"}]}
        text = "We share your phone number with advertisers for marketing. " * 10
        with patch.object(dashboard, 'extract_pipeline', return_value=fake):
            analysed = json.loads(self.client.post('/api/analyze-policy', json={"text": text, "url": "https://round.example/privacy"}).data)
        self.assertIn("entity_sources", analysed)
        self.assertIn("Phone Number", analysed["entity_sources"])
        saved = self.client.post('/api/save-service', json=analysed)
        self.assertEqual(saved.status_code, 201)
        portfolio = json.loads(self.client.get('/api/portfolio').data)
        names = [s["service_name"] for s in portfolio["services"]]
        self.assertIn("Round", names)


class TestFailurePaths(unittest.TestCase):

    def setUp(self):
        self.client = dashboard.app.test_client()

    def test_empty_text_is_rejected(self):
        resp = self.client.post('/api/analyze-policy', json={"text": "   "})
        self.assertEqual(resp.status_code, 400)

    def test_extraction_failure_returns_error_not_crash(self):
        with patch.object(dashboard, 'extract_pipeline', side_effect=RuntimeError("model unavailable")):
            resp = self.client.post('/api/analyze-policy', json={"text": "x" * 400})
        self.assertEqual(resp.status_code, 500)
        self.assertIn("model unavailable", json.loads(resp.data)["error"])

    def test_very_long_policy_is_partial_and_bounded(self):
        clause = "We share your location data with advertising partners for marketing. "
        text = clause * 1000  # about 80,000 characters
        fake = {"service_name": "Long", "mode": "MOCK/DEV",
                "clauses": [{"text": clause, "entities": ["Location"], "severity_score": 5, "specificity_score": 5}] * 15}
        with patch.object(dashboard, 'extract_pipeline', return_value=fake):
            data = json.loads(self.client.post('/api/analyze-policy', json={"text": text, "truncated": True}).data)
        self.assertEqual(data["coverage"]["status"], "partial")
        self.assertEqual(data["risk_score"], 100.0)
        self.assertTrue(data["coverage"]["is_demo"])


if __name__ == '__main__':
    unittest.main()

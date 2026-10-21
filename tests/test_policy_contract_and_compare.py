import unittest
import os
import sys
import json
from unittest.mock import patch

# Ensure project root and src are importable
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, ROOT)

from dashboard import app
from risk import (
    is_plausible_privacy_policy,
    calibrate_score,
    get_risk_band,
    classify_clause_type,
    get_clause_guidance
)
from extract import extract_pipeline

class TestPolicyPlausibility(unittest.TestCase):
    """
    Task 2 Tests:
    - Scanned text must be a real privacy policy.
    - GitHub-style and README-style pages are rejected.
    - Real policy pages are accepted.
    - Excerpts must come from the scanned policy text.
    """

    def setUp(self):
        self.client = app.test_client()
        self.client.testing = True

    def test_github_page_is_rejected(self):
        github_text = (
            "master 4 Branches 0 Tags 15 Commits. Clone with HTTPS: https://github.com/example/repo. "
            "Readme.md: ClauseGuard student prototype. Latest commit 3 hours ago by contributor. "
            "Run python run_demo.py to start. License MIT."
        )
        resp = self.client.post('/api/analyze-policy', json={
            "text": github_text,
            "url": "https://github.com/example/repo",
            "title": "GitHub - example/repo"
        })
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data["status"], "not_a_policy")
        self.assertEqual(
            data["message"],
            "This page doesn't look like a privacy policy. Open the policy page directly or paste the text."
        )
        self.assertEqual(len(data["clauses"]), 0)

    def test_readme_page_is_rejected(self):
        readme_text = (
            "# ClauseGuard Prototype\n\n"
            "ClauseGuard is a student prototype for analyzing policies. "
            "Features include SQLite database, Chrome extension, and scoring engine. "
            "Requirements: Python 3.9+. Installation: pip install -r requirements.txt. "
            "Run python src/dashboard.py to launch."
        )
        resp = self.client.post('/api/analyze-policy', json={
            "text": readme_text,
            "url": "https://example.com/project/readme",
            "title": "ClauseGuard README"
        })
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data["status"], "not_a_policy")
        self.assertEqual(
            data["message"],
            "This page doesn't look like a privacy policy. Open the policy page directly or paste the text."
        )
        self.assertEqual(len(data["clauses"]), 0)

    def test_real_policy_is_accepted_and_returns_contract(self):
        real_policy = (
            "Privacy Policy: We collect personal information when you register for our services. "
            "We may collect your IP address, device location, and email address. "
            "We share personal data with advertising partners and third-party vendors for analytics. "
            "We retain personal records for as long as necessary. You may opt out of promotional messages."
        )
        resp = self.client.post('/api/analyze-policy', json={
            "text": real_policy,
            "url": "https://example.com/privacy",
            "title": "Example Privacy Policy"
        })
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data["status"], "ok")
        self.assertIsNone(data["message"])
        self.assertIn("score", data)
        self.assertIn("band", data)
        self.assertIn(data["band"], ["very_low", "low", "typical", "high", "very_high"])
        self.assertTrue(len(data["clauses"]) > 0)
        
        # Output contract verification on each clause
        for clause in data["clauses"]:
            self.assertIn("type", clause)
            self.assertIn("meaning", clause)
            self.assertIn("what_you_can_do", clause)
            self.assertIn("excerpt", clause)
            # Rule: Never return an excerpt that did not come from the scanned policy text
            self.assertIn(clause["excerpt"], real_policy)

class TestScoringAndBands(unittest.TestCase):
    """
    Task 3 Tests:
    - Calibrated scoring maps median reference to typical band.
    - 5 bands: very_low, low, typical, high, very_high.
    """

    def test_bands_mapping(self):
        self.assertEqual(get_risk_band(10), "very_low")
        self.assertEqual(get_risk_band(20), "low")
        self.assertEqual(get_risk_band(35), "low")
        self.assertEqual(get_risk_band(40), "typical")
        self.assertEqual(get_risk_band(50), "typical")
        self.assertEqual(get_risk_band(60), "high")
        self.assertEqual(get_risk_band(75), "high")
        self.assertEqual(get_risk_band(80), "very_high")
        self.assertEqual(get_risk_band(95), "very_high")

    def test_calibration_maps_median_to_50(self):
        # Default reference median is 78.0
        calibrated_median = calibrate_score(78.0, ref_median=78.0)
        self.assertEqual(calibrated_median, 50)
        self.assertEqual(get_risk_band(calibrated_median), "typical")

    def test_calibration_spread(self):
        # Very safe service (raw risk 15)
        low_cal = calibrate_score(15.0, ref_median=78.0)
        self.assertTrue(0 <= low_cal < 20)
        self.assertEqual(get_risk_band(low_cal), "very_low")

        # Typical service (raw risk 75)
        typ_cal = calibrate_score(75.0, ref_median=78.0)
        self.assertTrue(40 <= typ_cal <= 60)
        self.assertEqual(get_risk_band(typ_cal), "typical")

        # Extremely aggressive service (raw risk 98)
        high_cal = calibrate_score(98.0, ref_median=78.0)
        self.assertTrue(high_cal > 80)
        self.assertEqual(get_risk_band(high_cal), "very_high")

class TestCompareEndpoint(unittest.TestCase):
    """
    Task 5 Tests:
    - Compare endpoint scans a service by name or URL.
    - Returns the exact output contract.
    - Works for a service not yet in the portfolio.
    """

    def setUp(self):
        self.client = app.test_client()
        self.client.testing = True

    def test_compare_unsaved_service_with_text(self):
        policy_text = (
            "We collect your personal information and contact details. "
            "We share your location data and device telemetry with third-party vendors. "
            "We retain personal records for up to 30 days."
        )
        payload = {
            "service": "BrandNewUnsavedApp",
            "text": policy_text,
            "url": "https://brandnewapp.com/privacy"
        }
        resp = self.client.post('/api/compare', json=payload)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)

        # Check Output Contract
        self.assertEqual(data["service"], "BrandNewUnsavedApp")
        self.assertEqual(data["policy_url"], "https://brandnewapp.com/privacy")
        self.assertIn("score", data)
        self.assertIn("band", data)
        self.assertEqual(data["status"], "ok")
        self.assertIsNone(data["message"])
        self.assertIsInstance(data["clauses"], list)
        self.assertTrue(len(data["clauses"]) > 0)

        first_clause = data["clauses"][0]
        self.assertIn("type", first_clause)
        self.assertIn("meaning", first_clause)
        self.assertIn("what_you_can_do", first_clause)
        self.assertIn("excerpt", first_clause)
        self.assertIn(first_clause["excerpt"], policy_text)

    def test_compare_non_policy_text_returns_not_a_policy(self):
        payload = {
            "service": "NonPolicyService",
            "text": "master 4 branches clone repo commits download zip readme",
            "url": "https://example.org/code"
        }
        resp = self.client.post('/api/compare', json=payload)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data["status"], "not_a_policy")
        self.assertEqual(
            data["message"],
            "This page doesn't look like a privacy policy. Open the policy page directly or paste the text."
        )
        self.assertEqual(data["clauses"], [])

if __name__ == '__main__':
    unittest.main()

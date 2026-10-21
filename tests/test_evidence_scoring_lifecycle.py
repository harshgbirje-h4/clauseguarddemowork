import unittest
import os
import sys
import json

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, ROOT)

from risk import (
    is_negated_claim,
    inspect_policy_statement,
    get_presentation_verdict,
    segment_policy_document,
    policy_risk_score,
    coverage_report,
    calibrate_score,
    get_risk_band
)
from extract import extract_pipeline
from dashboard import app

class TestLinguisticNegationsAndExceptions(unittest.TestCase):
    """
    Verification of all 7 linguistic negation, exception, contrastive,
    and conditional disclosure patterns.
    """

    def test_case_1_clean_negation(self):
        # "We do not sell your personal data."
        text = "We do not sell your personal data."
        info = inspect_policy_statement(text)
        self.assertTrue(info["is_protective_commitment"])
        self.assertFalse(info["has_exception"])
        self.assertFalse(info["has_contrastive_affirmation"])
        self.assertIn("data_selling", info["denied_practices"])
        self.assertEqual(len(info["confirmed_practices"]), 0)
        self.assertTrue(is_negated_claim(text))

    def test_case_2_affirmative_conditional_sale(self):
        # "We may sell certain data under specified circumstances."
        text = "We may sell certain data under specified circumstances."
        info = inspect_policy_statement(text)
        self.assertFalse(info["is_protective_commitment"])
        self.assertTrue(info["is_conditional"])
        self.assertIn("data_selling", info["confirmed_practices"])
        self.assertFalse(is_negated_claim(text))

    def test_case_3_negation_with_exception(self):
        # "We do not sell data except where legally permitted."
        text = "We do not sell data except where legally permitted."
        info = inspect_policy_statement(text)
        self.assertFalse(info["is_protective_commitment"])
        self.assertTrue(info["has_exception"])
        self.assertIn("data_selling", info["denied_practices"])
        self.assertIn("qualified_data_selling", info["confirmed_practices"])
        # Must not receive an unqualified protective pass
        self.assertFalse(is_negated_claim(text))

    def test_case_4_contrastive_third_party_sale(self):
        # "We do not sell data, but third-party partners may do so."
        text = "We do not sell data, but third-party partners may do so."
        info = inspect_policy_statement(text)
        self.assertFalse(info["is_protective_commitment"])
        self.assertTrue(info["has_contrastive_affirmation"])
        self.assertIn("data_selling", info["confirmed_practices"])
        self.assertFalse(is_negated_claim(text))

    def test_case_5_denies_one_confirms_another(self):
        # "We do not sell your personal data, but we share your browsing history with advertisers for targeted ads."
        text = "We do not sell your personal data, but we share your browsing history with advertisers for targeted ads."
        info = inspect_policy_statement(text)
        self.assertFalse(info["is_protective_commitment"])
        self.assertTrue(info["has_contrastive_affirmation"])
        self.assertIn("data_selling", info["denied_practices"])
        self.assertIn("targeted_advertising", info["confirmed_practices"])
        self.assertIn("third_party_sharing", info["confirmed_practices"])
        self.assertFalse(is_negated_claim(text))

    def test_case_6_negation_intervening_text(self):
        # "We do not, under any circumstances, sell your personal data."
        text = "We do not, under any circumstances, sell your personal data."
        info = inspect_policy_statement(text)
        self.assertTrue(info["is_protective_commitment"])
        self.assertFalse(info["has_exception"])
        self.assertIn("data_selling", info["denied_practices"])
        self.assertTrue(is_negated_claim(text))

        # "We will not, without your prior express consent, sell or share your data."
        text2 = "We will not, without your prior express consent, sell or share your data."
        info2 = inspect_policy_statement(text2)
        self.assertTrue(info2["is_protective_commitment"])
        self.assertTrue(is_negated_claim(text2))

    def test_case_7_conditional_hypothetical(self):
        # "If you connect your social media account, we may share your profile data with marketing affiliates."
        text = "If you connect your social media account, we may share your profile data with marketing affiliates."
        info = inspect_policy_statement(text)
        self.assertFalse(info["is_protective_commitment"])
        self.assertTrue(info["is_conditional"])
        self.assertIn("third_party_sharing", info["confirmed_practices"])
        self.assertFalse(is_negated_claim(text))

    def test_pipeline_integration_negation_and_exceptions(self):
        client = app.test_client()
        client.testing = True

        policy = (
            "Privacy Statement. We do not sell your personal data. "
            "We do not sell data, but third-party partners may do so. "
            "We collect cookies and device identifiers for analytics. "
            "You may request deletion of your information in settings."
        ) * 3

        resp = client.post('/api/analyze-policy', json={
            "text": policy,
            "url": "https://example.com/privacy"
        })
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)

        # Check that contrastive clause was captured as an active third-party disclosure
        sharing = data.get("sharing_findings", [])
        has_contrast_finding = any(item.get("has_contrast") for item in sharing)
        self.assertTrue(has_contrast_finding)


class TestThinEvidenceGuardAndBoundaries(unittest.TestCase):
    """
    Validates fixed, defensible presentation risk bands and boundary values:
    - Green (0–29): Lower Risk (only with sufficient evidence >= 2 clauses)
    - Amber (30–59): Moderate Risk
    - Red (60–100): Elevated Risk
    - Insufficient evidence -> Unable to assess (Gray)
    """

    def test_boundary_values_with_sufficient_evidence(self):
        cov = {"status": "complete", "clauses_found": 5}

        # 0.0 & 29.9 -> Lower Risk (Green)
        v0 = get_presentation_verdict(0.0, cov)
        self.assertEqual(v0["verdict"], "Lower Risk")
        self.assertEqual(v0["color"], "green")

        v29 = get_presentation_verdict(29.9, cov)
        self.assertEqual(v29["verdict"], "Lower Risk")
        self.assertEqual(v29["color"], "green")

        # 30.0 & 59.9 -> Moderate Risk (Amber)
        v30 = get_presentation_verdict(30.0, cov)
        self.assertEqual(v30["verdict"], "Moderate Risk")
        self.assertEqual(v30["color"], "amber")

        v59 = get_presentation_verdict(59.9, cov)
        self.assertEqual(v59["verdict"], "Moderate Risk")
        self.assertEqual(v59["color"], "amber")

        # 60.0 & 100.0 -> Elevated Risk (Red)
        v60 = get_presentation_verdict(60.0, cov)
        self.assertEqual(v60["verdict"], "Elevated Risk")
        self.assertEqual(v60["color"], "red")

        v100 = get_presentation_verdict(100.0, cov)
        self.assertEqual(v100["verdict"], "Elevated Risk")
        self.assertEqual(v100["color"], "red")

    def test_few_clauses_cannot_get_low_risk_verdict(self):
        """
        Critical Rule: A website must not receive a low-risk or safe verdict
        merely because the extractor found few clauses.
        """
        # 1 mild clause found: score is low (e.g. 15), but evidence is thin
        thin_cov = {"status": "complete", "clauses_found": 1}
        v_thin = get_presentation_verdict(15.0, thin_cov)
        self.assertEqual(v_thin["verdict"], "Insufficient Evidence")
        self.assertEqual(v_thin["label"], "Unable to assess")
        self.assertEqual(v_thin["color"], "gray")
        self.assertIsNone(v_thin["band_key"])

        # 0 clauses found: also insufficient
        zero_cov = {"status": "insufficient", "clauses_found": 0}
        v_zero = get_presentation_verdict(0.0, zero_cov)
        self.assertEqual(v_zero["verdict"], "Insufficient Evidence")
        self.assertEqual(v_zero["label"], "Unable to assess")

        # BUT: 1 severe clause (e.g. 80.0) MUST still alert the user to Elevated Risk!
        v_severe = get_presentation_verdict(80.0, thin_cov)
        self.assertEqual(v_severe["verdict"], "Elevated Risk")
        self.assertEqual(v_severe["color"], "red")

    def test_malformed_and_missing_inputs(self):
        cov = {"status": "complete", "clauses_found": 5}
        self.assertEqual(get_presentation_verdict(None, cov)["label"], "Unable to assess")
        self.assertEqual(get_presentation_verdict("bad_input", cov)["label"], "Unable to assess")
        self.assertEqual(get_presentation_verdict(False, cov)["label"], "Unable to assess")


class TestBoundedChunkingForLargePolicies(unittest.TestCase):
    """
    Validates document processing for policies > 50,000 characters up to 250k characters.
    Eliminates hard truncation and verifies character offset provenance.
    """

    def test_segment_large_document(self):
        paragraph = (
            "We collect your device identifiers, IP address, and cookie records. "
            "We do not sell personal data to advertisers. "
            "You may exercise your data deletion rights by contacting support.\n\n"
        )
        repeats = 70000 // len(paragraph) + 1
        large_text = paragraph * repeats
        self.assertGreater(len(large_text), 50000)

        meta = segment_policy_document(large_text, chunk_size=12000, overlap=1000, max_chars=250000)
        self.assertGreater(meta["chunk_count"], 1)
        self.assertFalse(meta["is_truncated"])
        self.assertEqual(meta["total_chars"], len(large_text))

        # Check that chunks preserve text integrity and valid offsets
        for chunk in meta["chunks"]:
            start = chunk["char_start"]
            end = chunk["char_end"]
            self.assertEqual(large_text[start:end], chunk["text"])

    def test_pipeline_extracts_from_large_document_with_offsets(self):
        padding = "This general section describes service functionality and user guidelines. " * 450
        target_clause = "We collect your facial biometric data for security authentication."
        full_text = f"Privacy Policy Header. {padding}\n\n{target_clause}\n\n{padding}"
        self.assertGreater(len(full_text), 50000)

        res = extract_pipeline(full_text, "LargeService")
        self.assertGreater(res["total_chars"], 50000)
        self.assertFalse(res["is_truncated"])
        self.assertGreater(res["chunks_processed"], 1)

        for c in res["clauses"]:
            start = c["char_start"]
            end = c["char_end"]
            excerpt = c["excerpt"]
            self.assertEqual(full_text[start:end], excerpt)
            self.assertTrue(c["is_verified"])
            self.assertEqual(c["confidence"], 1.0)


class TestScanLifecycleAndPlausibility(unittest.TestCase):
    """
    Tests scan lifecycle states:
    - plausible policy -> ok
    - non-policy (github / code) -> not_a_policy
    - thin text (< 300 chars) -> insufficient_evidence
    """

    def setUp(self):
        self.client = app.test_client()
        self.client.testing = True

    def test_insufficient_evidence_state(self):
        resp = self.client.post('/api/analyze-policy', json={
            "text": "Privacy notice: Hello.",
            "url": "https://example.com/short"
        })
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data["status"], "insufficient_evidence")
        self.assertIsNone(data["score"])
        self.assertIsNone(data["band"])
        self.assertEqual(data["presentation_verdict"]["label"], "Unable to assess")

    def test_real_policy_produces_success_lifecycle(self):
        real_policy = (
            "ClauseGuard Demo Privacy Policy. We collect your IP address, device identifier, and email address. "
            "We share your location data with third-party service providers. "
            "We retain your data for thirty days. You have the right to request deletion of your information."
        ) * 5
        resp = self.client.post('/api/analyze-policy', json={
            "text": real_policy,
            "url": "https://example.com/privacy"
        })
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data["status"], "ok")
        self.assertIsNotNone(data["score"])
        self.assertIn(data["band"], ["very_low", "low", "typical", "high", "very_high"])
        self.assertIn(data["presentation_verdict"]["verdict"], ["Lower Risk", "Moderate Risk", "Elevated Risk"])


if __name__ == '__main__':
    unittest.main()

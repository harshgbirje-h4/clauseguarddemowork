import unittest
import os
import json
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

class TestUIContractsAndProhibitions(unittest.TestCase):
    def test_mock_files_exist_and_conform_to_contract(self):
        mock_dir = os.path.join(ROOT, 'extension', 'mock')
        self.assertTrue(os.path.isdir(mock_dir), "extension/mock directory must exist")

        expected_files = [
            'mock_scan_ok.json',
            'mock_scan_not_a_policy.json',
            'mock_scan_blocked.json',
            'mock_compare_unsaved.json'
        ]

        for fname in expected_files:
            fpath = os.path.join(mock_dir, fname)
            self.assertTrue(os.path.isfile(fpath), f"Mock file {fname} must exist")

            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Contract verification
            self.assertIn("service", data)
            self.assertIn("policy_url", data)
            self.assertIn("policy_url_source", data)
            self.assertIn("score", data)
            self.assertIn("band", data)
            self.assertIn("status", data)
            self.assertIn("message", data)
            self.assertIn("clauses", data)
            self.assertIsInstance(data["clauses"], list)

            # Rule: mock data must not contain any real service's score
            for real_svc in ["Spotify", "Google", "Facebook", "Meta", "Microsoft", "Apple", "Amazon", "Twitter"]:
                self.assertNotEqual(data["service"].lower(), real_svc.lower(), f"Mock data must not use real service {real_svc}")

            if data["status"] == "ok":
                self.assertIsNotNone(data["score"])
                self.assertIn(data["band"], ["very_low", "low", "typical", "high", "very_high"])
                for clause in data["clauses"]:
                    self.assertIn("type", clause)
                    self.assertIn("meaning", clause)
                    self.assertIn("what_you_can_do", clause)
                    self.assertIn("excerpt", clause)
            elif data["status"] in ["not_a_policy", "blocked"]:
                self.assertIsNone(data["score"])
                self.assertIsNone(data["band"])
                self.assertIsNotNone(data["message"])

    def test_prohibited_jargon_is_absent_from_ui_files(self):
        prohibited_words = [
            "canonical",
            "clause entity",
            "severity",
            "specificity",
            "marginal risk",
            "additive",
            "de-duplicated",
            "w_overlap"
        ]

        ui_files = [
            os.path.join(ROOT, 'src', 'static', 'index.html'),
            os.path.join(ROOT, 'extension', 'popup.html'),
            os.path.join(ROOT, 'extension', 'popup.js'),
            os.path.join(ROOT, 'extension', 'popup.css'),
            os.path.join(ROOT, 'extension', 'content.js')
        ]

        for fpath in ui_files:
            self.assertTrue(os.path.isfile(fpath), f"{fpath} must exist")
            with open(fpath, 'r', encoding='utf-8') as f:
                content = f.read().lower()

            for word in prohibited_words:
                self.assertNotIn(
                    word,
                    content,
                    f"Prohibited word '{word}' found in user-facing file {os.path.basename(fpath)}"
                )

    def test_dashboard_combo_box_order(self):
        index_html_path = os.path.join(ROOT, 'src', 'static', 'index.html')
        with open(index_html_path, 'r', encoding='utf-8') as f:
            html = f.read()

        # Check Service combo box exists above URL field
        svc_pos = html.find('id="scan-service-input"')
        url_pos = html.find('id="scan-url"')
        text_pos = html.find('id="scan-text"')

        self.assertNotEqual(svc_pos, -1, "scan-service-input combo box must exist")
        self.assertNotEqual(url_pos, -1, "scan-url field must exist")
        self.assertNotEqual(text_pos, -1, "scan-text field must exist")
        self.assertTrue(svc_pos < url_pos < text_pos, "Service combo box must be above URL field, which must be above policy text box")

    def test_popup_layout_order(self):
        popup_html_path = os.path.join(ROOT, 'extension', 'popup.html')
        with open(popup_html_path, 'r', encoding='utf-8') as f:
            html = f.read()

        site_card_pos = html.find('id="site-card"')
        status_pos = html.find('id="status"')
        reminder_pos = html.find('id="unscanned-reminder"')
        score_pos = html.find('id="card-score-summary"')
        compare_pos = html.find('id="compare-section"')
        clauses_pos = html.find('id="card-clauses-section"')

        self.assertNotEqual(site_card_pos, -1)
        self.assertNotEqual(reminder_pos, -1)
        self.assertNotEqual(score_pos, -1)
        self.assertNotEqual(compare_pos, -1)
        self.assertNotEqual(clauses_pos, -1)

        # ITEM 2: Layout order: Site overview -> Score -> Compare directly below score -> Clauses
        self.assertTrue(site_card_pos < score_pos < compare_pos < clauses_pos,
                        "Popup must place Site card first, Score second, Compare directly below score, and Clauses details next")

if __name__ == '__main__':
    unittest.main()

import unittest
import os
import sys
import json

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from evaluation.ablation import run_ablation_experiment

class TestAblationStudy(unittest.TestCase):
    
    def test_ablation_experiment_execution(self):
        # Force mock mode
        if "GEMINI_API_KEY" in os.environ:
            del os.environ["GEMINI_API_KEY"]
            
        result = run_ablation_experiment()
        
        self.assertIn("dataset_version", result)
        self.assertIn("dataset_size", result)
        self.assertEqual(result["dataset_size"], 40)
        self.assertEqual(result["evaluation_mode"], "MOCK/DEV")
        
        # Check naive
        # Derive the expected naive counts from the labels, so the test does not
        # depend on a hardcoded copy of the dataset.
        import json as _json
        gt_path = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')),
                               'data', 'evaluation', 'ground_truth.json')
        with open(gt_path, encoding='utf-8') as f:
            labels = [ex["label"] for ex in _json.load(f)["examples"]]
        positives = sum(labels)
        negatives = len(labels) - positives
        naive = result["approaches"]["Naive"]
        self.assertEqual(naive["TP"], positives)
        self.assertEqual(naive["FP"], negatives)
        self.assertEqual(naive["FN"], 0)
        self.assertEqual(naive["TN"], 0)
        self.assertAlmostEqual(naive["Precision"], positives / len(labels))
        self.assertEqual(naive["Recall"], 1.0)
        
        # Check prefilter metrics exist
        prefilter = result["approaches"]["Prefilter"]
        self.assertIn("Precision", prefilter)
        self.assertIn("Recall", prefilter)
        self.assertIn("F1", prefilter)
        
        # Check composite deferral
        self.assertEqual(result["approaches"]["Composite"]["metrics"], "N/A")
        self.assertIn("deferred", result["approaches"]["Composite"]["limitations"].lower())
        
        # Check output file was created
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        out_path = os.path.join(base_dir, 'data', 'evaluation', 'ablation_results.json')
        self.assertTrue(os.path.exists(out_path))

if __name__ == '__main__':
    unittest.main()

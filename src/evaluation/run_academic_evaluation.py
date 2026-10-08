import os
import sys
import json
from dotenv import load_dotenv

# Load environment variables from the project root.
base_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
load_dotenv(os.path.join(base_dir, ".env"))

# Ensure src is in the Python path.
sys.path.insert(0, os.path.join(base_dir, "src"))

from extraction.prefilter import PrivacyPrefilter
from extraction.llm_extractor import LLMExtractor
from canonicalize import EntityCanonicalizer


def run_evaluation():
    print("Starting ClauseGuard academic evaluation...")

    if not os.getenv("GEMINI_API_KEY"):
        sys.exit(
            "ERROR: GEMINI_API_KEY was not found. "
            "Check the .env file in the project root."
        )

    gt_path = os.path.join(
        base_dir, "data", "evaluation", "ground_truth.json"
    )

    with open(gt_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    examples = dataset["examples"]
    if not examples:
        sys.exit("ERROR: The evaluation dataset contains no examples.")

    print(f"Loaded {len(examples)} annotated clauses.")

    prefilter = PrivacyPrefilter()
    prefilter.train_with_minimal_fixture()

    extractor = LLMExtractor("EvalService")
    canonicalizer = EntityCanonicalizer()

    y_true_binary = []
    candidate_map = {}
    entity_true = []

    # 1. Prefilter clauses and prepare ground truth.
    for i, ex in enumerate(examples):
        y_true_binary.append(int(ex["label"]))

        canon_true = set()
        for entity in ex.get("entities", []):
            canonical = canonicalizer.canonicalize(entity)
            if canonical and not canonical.startswith("Unknown"):
                canon_true.add(canonical)

        entity_true.append(canon_true)

        passed = prefilter.filter_candidates([ex["text"]])
        if passed:
            candidate_map[i] = ex["text"]

    print(f"Prefilter passed {len(candidate_map)} of {len(examples)} clauses.")

    # 2. Run the extractor and verify the actual mode.
    extracted_clauses = []
    extraction_mode = "NOT_RUN"

    if candidate_map:
        print("Calling Gemini API...")
        try:
            result = extractor.extract(list(candidate_map.values()))
        except Exception as exc:
            sys.exit(f"ERROR: Extraction failed: {exc}")

        extraction_mode = result.get("mode", "UNKNOWN")
        print(f"Extraction mode: {extraction_mode}")

        if not extraction_mode.startswith("GEMINI"):
            sys.exit(
                "ERROR: The extractor did not confirm Gemini mode. "
                "No evaluation report was written."
            )

        extracted_clauses = result.get("clauses", [])
    else:
        sys.exit(
            "ERROR: The prefilter rejected every clause. "
            "No evaluation report was written."
        )

    # 3. Match extracted clauses to the original examples.
    extracted_dict = {
        clause["text"]: clause
        for clause in extracted_clauses
        if "text" in clause
    }

    y_pred_binary = [0] * len(examples)
    entity_pred = [set() for _ in examples]
    classification_results = []

    for i, ex in enumerate(examples):
        text = ex["text"]

        if i in candidate_map and text in extracted_dict:
            y_pred_binary[i] = 1
            clause = extracted_dict[text]

            canon_pred = set()
            for entity in clause.get("entities", []):
                canonical = canonicalizer.canonicalize(entity)
                if canonical and not canonical.startswith("Unknown"):
                    canon_pred.add(canonical)

            entity_pred[i] = canon_pred

        classification_results.append({
            "id": ex["id"],
            "text": text,
            "true_label": y_true_binary[i],
            "pred_label": y_pred_binary[i],
            "true_entities": sorted(entity_true[i]),
            "pred_entities": sorted(entity_pred[i]),
        })

    # 4. Classification metrics.
    tp = sum(
        yt == 1 and yp == 1
        for yt, yp in zip(y_true_binary, y_pred_binary)
    )
    tn = sum(
        yt == 0 and yp == 0
        for yt, yp in zip(y_true_binary, y_pred_binary)
    )
    fp = sum(
        yt == 0 and yp == 1
        for yt, yp in zip(y_true_binary, y_pred_binary)
    )
    fn = sum(
        yt == 1 and yp == 0
        for yt, yp in zip(y_true_binary, y_pred_binary)
    )

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall else 0.0
    )

    total = tp + tn + fp + fn
    observed_agreement = (tp + tn) / total if total else 0.0

    p_yes = (
        ((tp + fp) * (tp + fn)) / (total * total)
        if total else 0.0
    )
    p_no = (
        ((tn + fn) * (tn + fp)) / (total * total)
        if total else 0.0
    )
    expected_agreement = p_yes + p_no

    kappa = (
        (observed_agreement - expected_agreement)
        / (1 - expected_agreement)
        if expected_agreement < 1 else 0.0
    )

    # 5. Entity Jaccard similarity.
    jaccard_scores = []

    for true_entities, predicted_entities in zip(entity_true, entity_pred):
        if not true_entities and not predicted_entities:
            continue

        union = true_entities | predicted_entities
        intersection = true_entities & predicted_entities

        if union:
            jaccard_scores.append(len(intersection) / len(union))

    avg_entity_accuracy = (
        sum(jaccard_scores) / len(jaccard_scores)
        if jaccard_scores else 0.0
    )

    # 6. Write the report only after successful Gemini extraction.
    report_path = os.path.join(
        base_dir, "Academic_Evaluation_Report.md"
    )

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# ClauseGuard Academic Evaluation Report\n\n")
        f.write("## 1. Evaluation Configuration\n")
        f.write(f"- **Dataset clauses:** {len(examples)}\n")
        f.write(f"- **Prefilter-passed clauses:** {len(candidate_map)}\n")
        f.write(f"- **Extraction mode:** {extraction_mode}\n")
        f.write("- **Ground truth:** `data/evaluation/ground_truth.json`\n\n")

        f.write("## 2. Classification Metrics\n")
        f.write(f"- **Precision:** {precision:.3f}\n")
        f.write(f"- **Recall:** {recall:.3f}\n")
        f.write(f"- **F1 Score:** {f1:.3f}\n")
        f.write(f"- **Cohen's Kappa:** {kappa:.3f}\n\n")

        f.write("## 3. Confusion Matrix\n")
        f.write("| | Predicted Positive | Predicted Negative |\n")
        f.write("|---|---:|---:|\n")
        f.write(f"| **Actual Positive** | TP: {tp} | FN: {fn} |\n")
        f.write(f"| **Actual Negative** | FP: {fp} | TN: {tn} |\n\n")

        f.write("## 4. Entity-Resolution Evaluation\n")
        f.write(
            "- **Mean Jaccard Similarity:** "
            f"{avg_entity_accuracy:.3f} / 1.0\n"
        )
        f.write(f"- **Clauses included in Jaccard mean:** {len(jaccard_scores)}\n\n")

        f.write("## 5. Classification Results\n")
        f.write("| ID | Clause Text | True Label | Predicted Label | True Entities | Predicted Entities |\n")
        f.write("|---|---|---:|---:|---|---|\n")

        for res in classification_results:
            text_short = (
                res["text"]
                if len(res["text"]) < 80
                else res["text"][:77] + "..."
            )
            true_entities = ", ".join(res["true_entities"]) or "None"
            pred_entities = ", ".join(res["pred_entities"]) or "None"

            f.write(
                f"| {res['id']} | {text_short} | "
                f"{res['true_label']} | {res['pred_label']} | "
                f"{true_entities} | {pred_entities} |\n"
            )

        f.write(
            "\n## 6. Interpretation and Limitations\n"
            "- These metrics measure performance against the supplied "
            "annotated dataset; they do not independently establish "
            "generalization to unseen policies.\n"
            "- ToS;DR correlation was not calculated by this evaluation "
            "script and is therefore not claimed here.\n"
            "- Results depend on the supplied annotations, prefilter, "
            "Gemini extraction response, and entity canonicalization.\n"
        )

    print("\nEvaluation complete.")
    print(f"Report saved to: {report_path}")
    print(f"Extraction mode: {extraction_mode}")
    print(f"Precision: {precision:.3f}")
    print(f"Recall: {recall:.3f}")
    print(f"F1 Score: {f1:.3f}")
    print(f"Cohen's Kappa: {kappa:.3f}")
    print(f"Mean entity Jaccard: {avg_entity_accuracy:.3f}")


if __name__ == "__main__":
    run_evaluation()


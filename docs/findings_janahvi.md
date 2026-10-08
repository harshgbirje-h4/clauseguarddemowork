# ClauseGuard: Technical Verification Findings (Janahvi)

## A. Confirmed results

**Evaluation (reported baseline, from Academic_Evaluation_Report.md)**
- Dataset: 40 clauses; 28 passed the prefilter; 20 ground-truth positive.
- Extraction mode: GEMINI, model `gemini-flash-lite-latest`.
- Precision 0.900, Recall 0.450, F1 0.600, Cohen's kappa 0.400.
- Confusion matrix: TP 9, FN 11, FP 1, TN 19.
- Mean entity Jaccard similarity: 0.397 across 21 included clauses (reported, not verified against code).
- Verified: the confusion matrix matches the report, the findings file, and the recomputed metrics. Ground-truth counts (40 total, 20 positive) match the confusion matrix.
- Not verified: the evaluation was not rerun.

**Evaluation method (verified from code)**
- `src/evaluation/run_academic_evaluation.py`, line 104 sets every prediction to 0. Lines 111–112 set a clause to 1 only if it passes the prefilter and is extracted.
- Verified by script run: 12 prefilter-rejected clauses, 0 of them ground-truth positive. All 11 false negatives therefore occur among the 28 clauses that passed the prefilter.

## B. Code present, not tested end to end

- In-page risk warning (`extension/content.js`): calls `POST /api/marginal-risk` and shows a warning when risk > 50 or new entities appear. Backend route exists in `src/dashboard.py`.
- Service comparison (`extension/popup.js`): calls `POST /api/quick-compare` and shows a warning or "safe" result. Backend route exists in `src/dashboard.py`.
- Status: wiring confirmed in code; not yet run.

**Code files present (presence only, not verified as working):** extraction (`extraction/prefilter.py`, `extraction/llm_extractor.py`, `extraction/validator.py`), canonicalization (`canonicalize.py`), scoring (`scoring.py`), marginal risk (`marginal.py`), storage (`db.py`), dashboard (`dashboard.py`).

## C. Limitations

- Dataset is AI-generated, with AI-generated ground-truth labels. Results are a preliminary synthetic-dataset evaluation and do not establish real-world accuracy or generalization.
- Recall is low (0.450): 11 of 20 positive clauses are missed. The misses occur at the classifier stage, not the prefilter.
- Entity overlap is limited (mean Jaccard 0.397, reported).
- Prefilter-rejected clauses are scored as negatives by design of the evaluation script.
- LLM output may vary between runs.
- No end-to-end test of the extension features has been completed.
- ToS;DR correlation was not evaluated.

## D. Verification log

- 5a verified: `run_academic_evaluation.py` line 104 sets `y_pred_binary = [0] * len(examples)`; lines 111–112 set positive predictions only when the clause is in `candidate_map` and `extracted_dict`.
- 5b verified: recomputed from TP 9, FP 1, FN 11, TN 19: N=40, precision 0.900, recall 0.450, F1 0.600, Cohen's kappa 0.400.
- 5c verified: `Academic_Evaluation_Report.md` reports TP 9, FN 11, FP 1, TN 19, GEMINI, `gemini-flash-lite-latest`, precision 0.900, recall 0.450, F1 0.600, kappa 0.400, mean Jaccard 0.397 (21 clauses). Report is not labeled mock. `Academic_Evaluation_Report_mock_backup.md` is excluded from sources.
- 5d verified: scan for unsupported terms returned only limitation statements (presence-only note, real-world accuracy limitation, ToS;DR not evaluated). No claims require rewriting.
- 12-clause check: 28 passed, 12 rejected, 0 rejected positives.

* **Technical preparation (Step 7):** Explained precision vs. recall, the prefilter result, negative-default evaluation logic, dataset limitations, Cohen’s kappa, and the untested extension features.

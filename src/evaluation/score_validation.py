"""
Check the clause risk formula against expert ratings.

Input: data/evaluation/scoring_ground_truth.json, with expert ratings per clause
(see its 'required_annotation_protocol'). Each example needs:
  severity_score / specificity_score  (the model-facing 1-5 ratings)
  human_clause_risk_score             (the expert's overall 0-100 rating)

Output: Spearman rank correlation between the formula (src/risk.py) and the
expert scores. Rank correlation is used because the formula and the experts
may use different scales; what matters is whether they order clauses the same way.

If there are no labelled examples the function says so and returns no number.
It never invents a correlation.
"""
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from risk import clause_risk_0_100

DEFAULT_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', '..', 'data', 'evaluation', 'scoring_ground_truth.json'))


def _average_ranks(values):
    """Ranks starting at 1, ties get the average rank."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(x, y):
    """Spearman rank correlation. Returns None if it is undefined (fewer than 2 points or no variance)."""
    if len(x) != len(y) or len(x) < 2:
        return None
    rx, ry = _average_ranks(x), _average_ranks(y)
    n = len(x)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sx = sum((a - mx) ** 2 for a in rx) ** 0.5
    sy = sum((b - my) ** 2 for b in ry) ** 0.5
    if sx == 0 or sy == 0:
        return None
    return cov / (sx * sy)


def validate_clause_scores(path=DEFAULT_PATH):
    with open(path, encoding='utf-8') as f:
        data = json.load(f)

    labelled = [ex for ex in data.get("examples", [])
                if ex.get("human_clause_risk_score") is not None]
    if not labelled:
        return {
            "status": "no_labels",
            "message": "No expert-rated clauses yet. Add examples to scoring_ground_truth.json before reporting a correlation.",
            "n": 0,
            "spearman": None,
        }

    formula = [clause_risk_0_100(ex.get("severity_score"), ex.get("specificity_score")) for ex in labelled]
    expert = [float(ex["human_clause_risk_score"]) for ex in labelled]
    rho = spearman(formula, expert)
    return {
        "status": "ok" if rho is not None else "undefined",
        "message": "Spearman correlation between the formula and expert ratings." if rho is not None
                   else "Correlation is undefined (no variation in one of the score sets).",
        "n": len(labelled),
        "spearman": None if rho is None else round(rho, 3),
    }


if __name__ == "__main__":
    print(json.dumps(validate_clause_scores(), indent=2))

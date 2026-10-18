"""
Bounded, explainable policy risk scoring.

Why this exists
---------------
The original analyze endpoint reported the SUM of clause scores. That grows
with the number of clauses, so a long but mild policy scored higher than a
short, dangerous one, and the value was not capped at 100.

The score here is:

  1. Clause risk (0-100)  = 100 * (severity / 5) * (specificity / 5)
     Severity and specificity are the 1-5 scales the extractor already uses.
  2. Policy risk (0-100)  = mean of the TOP_K highest clause risks.

Properties:
  * Always between 0 and 100.
  * Driven by the most severe clauses, so padding a policy with mild
    boilerplate does not change the score.
  * Easy to explain: "average risk of the 5 most severe clauses".

Coverage and category
---------------------
A risk number is only as good as the text behind it. `coverage_report`
records how much text was analysed and whether it was cut short, and
`risk_category` refuses to give a definitive band when the evidence is
too thin.
"""

TOP_K = 5
MIN_ANALYSABLE_CHARS = 300  # below this we do not claim a verdict

CATEGORY_BANDS = [
    (75.0, "Very High"),
    (50.0, "High"),
    (25.0, "Moderate"),
    (0.0, "Low"),
]


def _to_scale(value, lo=0.0, hi=5.0):
    """Return a float clamped to [lo, hi], or None if the value is not numeric."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return max(lo, min(hi, number))


def clause_risk_0_100(severity, specificity):
    """Risk of one clause on a 0-100 scale. Missing values count as 0."""
    sev = _to_scale(severity)
    spec = _to_scale(specificity)
    if sev is None or spec is None:
        return 0.0
    return 100.0 * (sev / 5.0) * (spec / 5.0)


def policy_risk_score(clauses, top_k=TOP_K):
    """
    Policy-level risk on a 0-100 scale: mean of the top_k clause risks.
    Returns 0.0 when there are no clauses.
    """
    risks = sorted(
        (clause_risk_0_100(c.get("severity_score"), c.get("specificity_score")) for c in clauses),
        reverse=True,
    )
    top = risks[:top_k]
    if not top:
        return 0.0
    return round(sum(top) / len(top), 1)


def coverage_report(analysed_chars, truncated, clauses_found, is_demo):
    """
    Describe how much evidence the verdict rests on.

    status:
      "complete" - the whole text we received was analysed
      "partial"  - the text was cut short before analysis
    """
    if clauses_found == 0 or analysed_chars < MIN_ANALYSABLE_CHARS:
        status = "insufficient"
    elif truncated:
        status = "partial"
    else:
        status = "complete"

    notes = []
    if truncated:
        notes.append("The policy was longer than the analysis limit, so only the first part was analysed.")
    if clauses_found == 0:
        notes.append("No privacy-relevant clauses were found in the text.")
    elif analysed_chars < MIN_ANALYSABLE_CHARS:
        notes.append("The text is too short to support a reliable verdict.")
    if is_demo:
        notes.append("This result came from the offline demo analyser, not the live model.")

    return {
        "status": status,
        "analysed_chars": analysed_chars,
        "truncated": bool(truncated),
        "clauses_found": clauses_found,
        "is_demo": bool(is_demo),
        "notes": notes,
    }


def risk_category(score, coverage):
    """
    Map a score to Low / Moderate / High / Very High, or 'Inconclusive'
    when the coverage is too thin to justify a band.
    """
    if coverage["status"] == "insufficient":
        return "Inconclusive"
    for threshold, label in CATEGORY_BANDS:
        if score >= threshold:
            return label
    return "Low"

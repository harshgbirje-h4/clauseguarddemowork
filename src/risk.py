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
MIN_CONFIDENT_CLAUSES = 2   # below this we refuse to declare a low-risk/safe verdict

CATEGORY_BANDS = [
    (75.0, "Very High"),
    (50.0, "High"),
    (25.0, "Moderate"),
    (0.0, "Low"),
]

# Standard 5 calibrated risk bands defined in docs/SCORING.md
FIVE_BANDS = [
    (80.0, 100.0, "very_high"),
    (60.0, 80.0, "high"),
    (40.0, 60.0, "typical"),
    (20.0, 40.0, "low"),
    (0.0, 20.0, "very_low"),
]

# Authoritative 3-tier presentation risk bands (Defensible & User-Facing):
# Green (0–29): Lower Risk
# Amber (30–59): Moderate Risk
# Red (60–100): Elevated Risk
PRESENTATION_BANDS = [
    (60.0, 100.0, "Elevated Risk", "red", "elevated_risk"),
    (30.0, 59.999, "Moderate Risk", "amber", "moderate_risk"),
    (0.0, 29.999, "Lower Risk", "green", "lower_risk"),
]

# Baseline uncalibrated median for typical commercial privacy policies
DEFAULT_REFERENCE_MEDIAN = 78.0

import re

# Exception markers that introduce carve-outs or conditional allowances
EXCEPTION_PATTERN = re.compile(
    r'\b(?:except|unless|excluding|other\s+than|with\s+the\s+exception\s+of|save\s+for|save\s+where)\b',
    re.IGNORECASE
)

# Contrastive conjunctions indicating a shift from denial to affirmative disclosure
CONTRASTIVE_PATTERN = re.compile(
    r'\b(?:but|however|although|whereas|while|yet|on\s+the\s+other\s+hand)\b',
    re.IGNORECASE
)

# Negation followed by verb, allowing intervening words (e.g. 'do not, under any circumstances, sell')
NEGATION_VERB_PATTERN = re.compile(
    r'\b(?:do\s+not|don\'t|does\s+not|doesn\'t|will\s+not|won\'t|never|neither|no|not|cannot|without\s+your\s+(?:express\s+|prior\s+)?consent)\b'
    r'(?:[^\w\n]*(?:[\w]+[^\w\n]*){0,8}?)'
    r'\b(?:sell|monetiz\w*|rent|trade|disclose|share|transfer)\b',
    re.IGNORECASE
)

# Active third-party selling / sharing affirmation following a contrastive shift
AFFIRMATIVE_THIRD_PARTY_PATTERN = re.compile(
    r'\b(?:third[\s-]part\w*|partner\w*|advertis\w*|network\w*|vendor\w*|affiliate\w*|we)\s+(?:may|do|will|can)\s+(?:sell|share|monetiz\w*|disclose|collect|track|use)\b',
    re.IGNORECASE
)

# Affirmative sale or commercial transfer
AFFIRMATIVE_SALE_PATTERN = re.compile(
    r'\b(?:we\s+(?:may|reserve\s+the\s+right\s+to|do|will)\s+sell|may\s+sell|sell\s+certain\s+data|commercial\s+sale|monetiz\w*\s+your\s+data)\b',
    re.IGNORECASE
)

# Conditional statements
CONDITIONAL_PATTERN = re.compile(
    r'\b(?:if\s+you|where\s+you|should\s+you|in\s+the\s+event|when\s+you\s+choose\s+to|to\s+the\s+extent\s+permitted)\b',
    re.IGNORECASE
)


def inspect_policy_statement(text):
    """
    Performs deterministic, rule-based linguistic inspection of privacy statements
    to discern clean protective commitments, exception clauses, contrastive affirmations,
    and conditional disclosures.
    """
    if not text or not isinstance(text, str):
        return {
            "is_protective_commitment": False,
            "has_exception": False,
            "has_contrastive_affirmation": False,
            "is_conditional": False,
            "denied_practices": [],
            "confirmed_practices": [],
            "grounded_reason": "Empty or non-textual input."
        }

    lower = text.lower().strip()
    has_neg_verb = bool(NEGATION_VERB_PATTERN.search(lower))
    has_exception = bool(EXCEPTION_PATTERN.search(lower))
    has_contrast = bool(CONTRASTIVE_PATTERN.search(lower))
    is_conditional = bool(CONDITIONAL_PATTERN.search(lower))
    has_aff_sale = bool(AFFIRMATIVE_SALE_PATTERN.search(lower))

    denied = []
    confirmed = []

    # Case 2: Affirmative conditional sale ("We may sell certain data under specified circumstances")
    if has_aff_sale and not has_neg_verb:
        confirmed.append("data_selling")
        return {
            "is_protective_commitment": False,
            "has_exception": has_exception,
            "has_contrastive_affirmation": False,
            "is_conditional": True,
            "denied_practices": [],
            "confirmed_practices": confirmed,
            "grounded_reason": "Affirmative disclosure indicates personal data may be commercially sold or transferred under specified circumstances."
        }

    # If there is a negation verb
    if has_neg_verb:
        if "sell" in lower or "monetiz" in lower:
            denied.append("data_selling")
        elif "share" in lower or "disclose" in lower:
            denied.append("third_party_sharing")

        # Case 4 & 5: Contrastive conjunction confirms third-party sharing or targeted ads
        # e.g., "We do not sell data, but third-party partners may do so"
        # e.g., "We do not sell your personal data, but we share your browsing history with advertisers"
        if has_contrast:
            contrast_parts = CONTRASTIVE_PATTERN.split(lower, maxsplit=1)
            after_contrast = contrast_parts[1] if len(contrast_parts) > 1 else ""
            if any(w in after_contrast for w in ["advertis", "targeted ad", "ad network", "marketing"]):
                confirmed.append("targeted_advertising")
            if any(w in after_contrast for w in ["share", "disclose", "partner", "vendor", "third part"]):
                confirmed.append("third_party_sharing")
            if "sell" in after_contrast or "monetiz" in after_contrast or ("do so" in after_contrast and "data_selling" in denied):
                confirmed.append("data_selling")

            if confirmed:
                return {
                    "is_protective_commitment": False,
                    "has_exception": has_exception,
                    "has_contrastive_affirmation": True,
                    "is_conditional": is_conditional,
                    "denied_practices": denied,
                    "confirmed_practices": confirmed,
                    "grounded_reason": f"Direct practice ({', '.join(denied)}) is denied, but contrastive clause confirms active practice ({', '.join(confirmed)})."
                }

        # Case 3: Exception clause ("We do not sell data except where legally permitted")
        if has_exception:
            confirmed.append("qualified_data_selling")
            return {
                "is_protective_commitment": False,
                "has_exception": True,
                "has_contrastive_affirmation": False,
                "is_conditional": True,
                "denied_practices": denied,
                "confirmed_practices": confirmed,
                "grounded_reason": "Statement denies commercial sale generally, but contains an explicit exception clause creating a permitted carve-out."
            }

        # Case 1 & 6: Clean protective commitment (including intervening qualifiers)
        # e.g. "We do not sell your personal data"
        # e.g. "We do not, under any circumstances, sell your personal data"
        return {
            "is_protective_commitment": True,
            "has_exception": False,
            "has_contrastive_affirmation": False,
            "is_conditional": is_conditional,
            "denied_practices": denied,
            "confirmed_practices": [],
            "grounded_reason": "Clean, unqualified negative commitment affirmed in source policy text."
        }

    # Case 7: Conditional disclosures without negation
    if any(w in lower for w in ["advertis", "marketing partner", "targeted ad"]):
        confirmed.append("targeted_advertising")
    if any(w in lower for w in ["share", "disclose", "third party", "vendor", "affiliate"]):
        confirmed.append("third_party_sharing")
    if any(w in lower for w in ["location", "gps", "geolocation"]):
        confirmed.append("location_tracking")

    return {
        "is_protective_commitment": False,
        "has_exception": has_exception,
        "has_contrastive_affirmation": False,
        "is_conditional": is_conditional,
        "denied_practices": [],
        "confirmed_practices": confirmed,
        "grounded_reason": "Affirmative policy disclosure."
    }


def is_negated_claim(text):
    """
    Returns True ONLY if the text represents an explicit, unqualified protective commitment
    (e.g. 'We do not sell your personal data', 'We do not, under any circumstances, sell').
    Returns False if the claim has exception clauses or contrastive affirmations.
    """
    info = inspect_policy_statement(text)
    return info["is_protective_commitment"]


def get_presentation_verdict(score, coverage=None):
    """
    Returns the authoritative presentation verdict:
    - Insufficient Evidence / Unable to assess: when evidence is lacking
    - Green (0–29): Lower Risk (requires sufficient evidence; never given merely for few clauses)
    - Amber (30–59): Moderate Risk
    - Red (60–100): Elevated Risk
    """
    cov_status = coverage.get("status") if coverage else "insufficient"
    clauses_found = coverage.get("clauses_found", 0) if coverage else 0

    if cov_status == "insufficient" or score is None or isinstance(score, bool):
        return {
            "verdict": "Insufficient Evidence",
            "label": "Unable to assess",
            "color": "gray",
            "band_key": None
        }

    try:
        s = float(score)
    except (ValueError, TypeError):
        return {
            "verdict": "Insufficient Evidence",
            "label": "Unable to assess",
            "color": "gray",
            "band_key": None
        }

    # Severe risk (>= 60) is grounded in direct evidence even if few clauses are found
    if s >= 60.0:
        return {
            "verdict": "Elevated Risk",
            "label": "Elevated Risk",
            "color": "red",
            "band_key": "elevated_risk"
        }

    # Thin evidence guard: A site must NOT receive a low-risk or safe verdict merely
    # because the extractor found few clauses (< MIN_CONFIDENT_CLAUSES).
    if clauses_found < MIN_CONFIDENT_CLAUSES:
        return {
            "verdict": "Insufficient Evidence",
            "label": "Unable to assess",
            "color": "gray",
            "band_key": None
        }

    if s >= 30.0:
        return {
            "verdict": "Moderate Risk",
            "label": "Moderate Risk",
            "color": "amber",
            "band_key": "moderate_risk"
        }
    else:
        return {
            "verdict": "Lower Risk",
            "label": "Lower Risk",
            "color": "green",
            "band_key": "lower_risk"
        }


def segment_policy_document(text, chunk_size=12000, overlap=1000, max_chars=250000):
    """
    Bounded document segmentation for large privacy policies up to max_chars (default 250k).
    Replaces hard truncation with overlapping semantic segments, preserving original
    character offsets for evidence traceability.
    """
    if not text or not isinstance(text, str):
        return {
            "chunks": [],
            "total_chars": 0,
            "processed_chars": 0,
            "is_truncated": False,
            "chunk_count": 0
        }

    total_chars = len(text)
    is_truncated = total_chars > max_chars
    effective_text = text[:max_chars]
    processed_chars = len(effective_text)

    if processed_chars <= chunk_size:
        return {
            "chunks": [{
                "index": 0,
                "text": effective_text,
                "char_start": 0,
                "char_end": processed_chars
            }],
            "total_chars": total_chars,
            "processed_chars": processed_chars,
            "is_truncated": is_truncated,
            "chunk_count": 1
        }

    chunks = []
    start = 0
    idx = 0

    while start < processed_chars:
        end = min(start + chunk_size, processed_chars)
        
        # If not at the end of the document, break cleanly on paragraph or sentence boundary
        if end < processed_chars:
            cut = effective_text.rfind('\n\n', start + chunk_size // 2, end)
            if cut == -1:
                cut = effective_text.rfind('. ', start + chunk_size // 2, end)
                if cut != -1:
                    cut += 1  # Include the period
            if cut != -1 and cut > start:
                end = cut

        chunks.append({
            "index": idx,
            "text": effective_text[start:end],
            "char_start": start,
            "char_end": end
        })
        idx += 1

        if end >= processed_chars:
            break

        # Move forward, stepping back by overlap
        start = max(end - overlap, start + 1)

    return {
        "chunks": chunks,
        "total_chars": total_chars,
        "processed_chars": processed_chars,
        "is_truncated": is_truncated,
        "chunk_count": len(chunks)
    }


def is_plausible_privacy_policy(text, url="", title=""):
    """
    Validates whether the provided text represents a plausible privacy policy.
    Rejects code repositories, README documentation, and landing pages that lack
    genuine policy commitments.
    """
    if not text or not isinstance(text, str):
        return False
    clean = text.strip()
    if len(clean) < 15:
        return False

    lower = clean.lower()

    # Reject GitHub/code repository interface pages (e.g., commit logs, branch selectors)
    import re
    if re.search(r'\b(branches|pull requests|commits|clone with https|clone or download)\b', lower):
        if not any(k in lower for k in ['privacy policy', 'personal information', 'personal data']):
            return False

    # Reject standard software documentation or project README headers
    if re.search(r'^(#\s+[a-zA-Z0-9_-]+\s*\n|\b(prototype for|requirements:|pip install|git clone|usage: python)\b)', lower):
        if not any(k in lower for k in ['privacy policy', 'personal information', 'personal data', 'we collect', 'we share']):
            return False

    # Policy language indicators (personal information, collection, sharing, retention, user rights)
    policy_terms = [
        'personal information', 'personal data', 'personally identifiable',
        'privacy policy', 'privacy notice', 'privacy statement', 'data protection',
        'policy', 'collect', 'share', 'retain', 'disclose', 'third party', 'third-party',
        'ip address', 'cookie', 'opt out', 'opt-out', 'log data', 'logged',
        'information we receive', 'rights'
    ]

    matches = [term for term in policy_terms if term in lower]
    return len(matches) >= 1


def get_risk_band(score):
    """
    Returns the machine-readable risk band key for a score on the 0-100 scale:
    0–20: very_low
    20–40: low
    40–60: typical
    60–80: high
    80–100: very_high
    """
    if score is None:
        return None
    try:
        s = float(score)
    except (ValueError, TypeError):
        return None

    if s >= 80.0:
        return "very_high"
    elif s >= 60.0:
        return "high"
    elif s >= 40.0:
        return "typical"
    elif s >= 20.0:
        return "low"
    else:
        return "very_low"


def calibrate_score(raw_score, ref_median=None):
    """
    Calibrates a raw policy score so that the empirical reference median
    maps to the center of the 'typical' band (50.0).
    Uses monotonic continuous piecewise linear calibration:
      - Raw 0.0 maps to 0
      - Raw ref_median maps to 50
      - Raw 100.0 maps to 100
    """
    if raw_score is None:
        return None
    try:
        r = float(raw_score)
    except (ValueError, TypeError):
        return 0

    if ref_median is None:
        ref_median = DEFAULT_REFERENCE_MEDIAN

    # Clamp to [0, 100]
    r = max(0.0, min(100.0, r))

    if ref_median <= 0.0 or ref_median >= 100.0:
        return int(round(r))

    if r <= ref_median:
        calibrated = 50.0 * (r / ref_median)
    else:
        calibrated = 50.0 + 50.0 * ((r - ref_median) / (100.0 - ref_median))

    return int(round(max(0.0, min(100.0, calibrated))))


def classify_clause_type(text, entities=None, category=None):
    """
    Maps an extracted clause into one of the 15 canonical taxonomy keys.
    """
    lower = (text or "").lower()
    ents = [e.lower() for e in (entities or [])]

    if any("location" in e for e in ents) or any(w in lower for w in ["location", "gps", "geolocation", "precise location"]):
        return "location_tracking"
    if any("cookie" in e for e in ents) or any(w in lower for w in ["cookie", "web beacon", "pixel tag", "tracking technology"]):
        return "cookies_tracking"
    if any("biometric" in e for e in ents) or any(w in lower for w in ["biometric", "face recognition", "fingerprint", "voiceprint"]):
        return "biometric_data"
    if any(w in lower for w in ["sell your", "selling", "sale of personal", "monetiz", "commercial value"]):
        return "data_selling"
    if any(w in lower for w in ["advertis", "marketing partner", "targeted ad", "ad network", "profiling"]):
        return "targeted_advertising"
    if any(w in lower for w in ["share", "disclose", "distribute", "third party", "third-party", "vendor", "affiliate", "partner"]):
        return "third_party_sharing"
    if any(w in lower for w in ["delete", "deletion", "erasure", "erase", "remove account", "close account"]):
        return "data_deletion"
    if any(w in lower for w in ["opt-out", "opt out", "unsubscribe", "opt out of"]):
        return "opt_out"
    if any(w in lower for w in ["access your", "portability", "statutory rights", "gdpr", "ccpa", "rectif", "subject access"]):
        return "user_rights"
    if any(w in lower for w in ["retain", "retention", "how long we keep", "storage period", "store your information"]):
        return "data_retention"
    if any(w in lower for w in ["security", "encryption", "safeguard", "protect your", "breach"]):
        return "data_security"
    if any(w in lower for w in ["child", "children", "minor", "under 13", "under 16"]):
        return "children_privacy"
    if any(w in lower for w in ["update this policy", "changes to this", "modify this policy", "amend"]):
        return "policy_changes"
    if any(w in lower for w in ["collect", "gather", "log data", "ip address", "device", "email", "phone", "information you provide"]):
        return "data_collection"

    return "data_collection" if ents else "other"


def get_clause_guidance(clause_type):
    """
    Returns guidance dict with 'meaning' and 'what_you_can_do'.
    Loads from data/guidance/clause_guidance.json if present; otherwise returns
    standard neutral defaults.
    """
    import os
    import json

    guidance_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'guidance', 'clause_guidance.json'))
    if os.path.exists(guidance_path):
        try:
            with open(guidance_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if clause_type in data:
                    return data[clause_type]
        except Exception:
            pass

    # Standard neutral defaults per taxonomy
    defaults = {
        "data_collection": {
            "meaning": "The service collects and stores user identifiers, usage records, or device data.",
            "what_you_can_do": "Review your account profile settings and minimize optional information shared."
        },
        "third_party_sharing": {
            "meaning": "Personal information may be disclosed to external service partners, vendors, or affiliates.",
            "what_you_can_do": "Check privacy settings to limit data sharing or opt out of non-essential third-party disclosures."
        },
        "data_selling": {
            "meaning": "User information may be transferred for commercial consideration or advertising monetization.",
            "what_you_can_do": "Exercise 'Do Not Sell My Personal Information' rights under applicable settings."
        },
        "targeted_advertising": {
            "meaning": "Activity and interests are tracked to deliver personalized or behavioral advertisements.",
            "what_you_can_do": "Disable personalized ad tracking in service settings and reset your device ad ID."
        },
        "data_retention": {
            "meaning": "Specifies criteria or timeframes for how long collected user data is kept.",
            "what_you_can_do": "Request periodic data review or account cleanup if retention periods are unspecified."
        },
        "data_security": {
            "meaning": "Describes security safeguards and encryption measures used to protect user records.",
            "what_you_can_do": "Enable two-factor authentication and use strong, unique passwords."
        },
        "user_rights": {
            "meaning": "Outlines statutory rights to access, inspect, correct, or export stored personal data.",
            "what_you_can_do": "Submit a privacy request or data subject access request to inspect your records."
        },
        "data_deletion": {
            "meaning": "Explains mechanisms to request account termination and erasure of personal data.",
            "what_you_can_do": "Initiate deletion in account settings or contact the privacy officer to erase records."
        },
        "opt_out": {
            "meaning": "Provides choices to opt out of marketing communications or non-essential telemetry.",
            "what_you_can_do": "Follow opt-out links in communications or toggle preference switches in account settings."
        },
        "cookies_tracking": {
            "meaning": "Uses browser cookies and local tracking technologies to monitor site activity.",
            "what_you_can_do": "Manage cookie preferences via the site banner or browser cookie settings."
        },
        "location_tracking": {
            "meaning": "Monitors or logs physical geolocation or real-time movement data.",
            "what_you_can_do": "Revoke location permissions in your browser or device system settings."
        },
        "biometric_data": {
            "meaning": "Processes sensitive biometric identifiers such as facial recognition or voiceprints.",
            "what_you_can_do": "Avoid enabling optional biometric features if standard authentication suffices."
        },
        "children_privacy": {
            "meaning": "Addresses privacy practices specifically concerning minors and children.",
            "what_you_can_do": "Verify parental consent options and child account controls if applicable."
        },
        "policy_changes": {
            "meaning": "Explains how updates or unilateral amendments to the privacy policy are announced.",
            "what_you_can_do": "Ensure your notification email is up to date to receive policy change alerts."
        },
        "other": {
            "meaning": "General terms and auxiliary privacy commitments governing the service.",
            "what_you_can_do": "Review the full privacy policy document for specific operational details."
        }
    }

    return defaults.get(clause_type, defaults["other"])


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


def coverage_report(analysed_chars, truncated, clauses_found, is_demo, total_chars=None, processed_chars=None):
    """
    Describe how much evidence the verdict rests on.

    status:
      "complete"     - the whole text we received was analysed
      "partial"      - the text was cut short before analysis
      "insufficient" - fewer than MIN_ANALYSABLE_CHARS or 0 clauses found
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
        "total_source_chars": total_chars if total_chars is not None else analysed_chars,
        "processed_chars": processed_chars if processed_chars is not None else analysed_chars,
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

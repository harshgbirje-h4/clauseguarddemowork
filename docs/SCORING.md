# ClauseGuard Scoring Specification & Data Contract

This document defines the standardized data contract, clause taxonomy, calibrated scoring model, and risk bands for ClauseGuard.

---

## 1. Output Contract

Every policy scan response (from the analysis pipeline, background extension scan, or compare endpoint) must conform strictly to the following JSON structure:

```json
{
  "service": "Microsoft",
  "policy_url": "https://...",
  "policy_url_source": "known_mapping" | "page_search",
  "score": 52,
  "band": "typical",
  "status": "ok" | "not_a_policy" | "blocked" | "error",
  "message": "human-readable message or null",
  "clauses": [
    {
      "type": "third_party_sharing",
      "meaning": "...",
      "what_you_can_do": "...",
      "excerpt": "original policy text"
    }
  ]
}
```

### Field Definitions:
* **`service`** *(string)*: Name of the identified digital service or provider.
* **`policy_url`** *(string)*: Verified URL to the privacy policy document.
* **`policy_url_source`** *(string)*: How the policy URL was resolved: `"known_mapping"` (from curated directory) or `"page_search"` (fallback DOM discovery).
* **`score`** *(number | null)*: Calibrated privacy risk score on a 0–100 scale (rounded integer). Null if `status` is not `"ok"`.
* **`band`** *(string | null)*: The corresponding risk band key (`very_low`, `low`, `typical`, `high`, `very_high`). Null if `status` is not `"ok"`.
* **`status`** *(string)*: Status code of the scan operation:
  * `"ok"`: Privacy policy successfully identified and analyzed.
  * `"not_a_policy"`: Provided text does not appear to be a privacy policy.
  * `"blocked"`: Automated fetch blocked by anti-bot protections or captcha.
  * `"error"`: Extraction or internal processing error.
* **`message`** *(string | null)*: Human-readable status or guidance message, or `null` when scan succeeds normally.
* **`clauses`** *(array)*: List of extracted policy clauses:
  * **`type`** *(string)*: Canonical clause-type key from the taxonomy below.
  * **`meaning`** *(string)*: Plain-language explanation of what this clause means for user privacy.
  * **`what_you_can_do`** *(string)*: Actionable guidance or control advice for the user.
  * **`excerpt`** *(string)*: Exact verbatim excerpt from the scanned policy text (must originate from the source document).

---

## 2. Clause-Type Taxonomy

Every extracted clause maps to one of the following canonical clause-type keys (used by `data/guidance/clause_guidance.json`):

1. **`data_collection`**: Collection of general personal data, identity information, device telemetry, or usage records.
2. **`third_party_sharing`**: Disclosing, transferring, or sharing user data with external corporate third parties or business partners.
3. **`data_selling`**: Selling personal data or exchanging personal information for commercial consideration/monetization.
4. **`targeted_advertising`**: Cross-site tracking, behavioral profiling, and delivering personalized or interest-based advertising.
5. **`data_retention`**: Duration, indefinite storage, or criteria governing how long collected data is retained.
6. **`data_security`**: Security safeguards, encryption measures, or notices regarding breach management.
7. **`user_rights`**: Statutory privacy rights (such as GDPR/CCPA rights to access, inspect, correct, or port personal data).
8. **`data_deletion`**: Procedures and rights for requesting account termination, data erasure, or deletion of stored records.
9. **`opt_out`**: Mechanisms allowing users to opt out of promotional communications, profiling, or non-essential telemetry.
10. **`cookies_tracking`**: Deployment of cookies, web beacons, tracking pixels, or browser local storage technologies.
11. **`location_tracking`**: Collection or processing of geolocation data, GPS coordinates, or real-time physical movement.
12. **`biometric_data`**: Processing of sensitive biometric identifiers, facial geometry, voice patterns, or health records.
13. **`children_privacy`**: Specific practices regarding minors, parental verification, or collection of children's data.
14. **`policy_changes`**: Procedures for notifying users about amendments, updates, or unilateral modifications to the policy terms.
15. **`other`**: General terms or auxiliary privacy clauses not falling into the specific categories above.

---

## 3. Risk Bands

Risk scores are grouped into five non-overlapping bands:

| Score Range | Band Key | Description |
|---|---|---|
| **0 – 20** | `very_low` | Minimal data collection, strict confidentiality, no commercial sharing. |
| **20 – 40** | `low` | Limited collection focused on core utility; conservative data practices. |
| **40 – 60** | `typical` | Industry-standard data practices for modern consumer web/mobile services. |
| **60 – 80** | `high` | Extensive behavioral tracking, third-party disclosures, or vague retention terms. |
| **80 – 100** | `very_high` | Broad commercial monetization, explicit selling of data, or unbounded sharing. |

---

## 4. Plain-Language Scoring Method

### Overview
1. **Clause Scoring**: Each extracted clause is assigned two standardized dimensions:
   * **Severity** ($1 \le \text{severity} \le 5$): How intrusive or privacy-sensitive the practice is.
   * **Specificity** ($1 \le \text{specificity} \le 5$): How specific or unbounded the clause language is.
   
   $$\text{Clause Risk} = 100 \times \left(\frac{\text{Severity}}{5.0}\right) \times \left(\frac{\text{Specificity}}{5.0}\right)$$

2. **Policy Baseline (Top-K Aggregation)**:
   A privacy policy's raw risk is driven by its most severe clauses, preventing a long policy padded with boilerplate from artificially inflating or deflating the score:
   $$\text{Raw Policy Score} = \frac{1}{K} \sum_{i=1}^K \text{Clause Risk}_{(i)} \quad (\text{for top } K=5 \text{ clauses})$$

3. **Calibration to Reference Distribution**:
   Because modern web platforms routinely extract several severe clauses (e.g., ad tracking, location, partner sharing), raw top-5 scores tend to cluster in the 75–95 range. Uncalibrated scoring makes almost every everyday app look dangerous.
   * To provide meaningful distinction, the raw score is calibrated against an empirical reference set of everyday services (`data/calibration/reference_services.json`).
   * The reference set median ($M_{\text{ref}}$) is calibrated to the center of the `typical` band ($\text{Score} = 50$).
   * Everyday applications (such as Instagram, LinkedIn, Microsoft Teams) land in the `typical` range ($40–60$), while services with safer-than-average or worse-than-average practices spread proportionately across `low`/`very_low` or `high`/`very_high`.

### Placeholder Worked Example
Consider an analysis of candidate service **Service X**:
* Extracted clauses produce the following top 5 clause evaluations:
  1. Clause 1 (Sharing with marketing networks): Severity 4.0, Specificity 4.0 $\rightarrow$ $\text{Risk} = 100 \times (4/5) \times (4/5) = 64.0$
  2. Clause 2 (Location telemetry tracking): Severity 4.0, Specificity 3.0 $\rightarrow$ $\text{Risk} = 100 \times (4/5) \times (3/5) = 48.0$
  3. Clause 3 (Persistent cookies & device IDs): Severity 3.0, Specificity 4.0 $\rightarrow$ $\text{Risk} = 100 \times (3/5) \times (4/5) = 48.0$
  4. Clause 4 (Account details & usage analytics): Severity 3.0, Specificity 3.0 $\rightarrow$ $\text{Risk} = 100 \times (3/5) \times (3/5) = 36.0$
  5. Clause 5 (Affiliate data transfer): Severity 3.0, Specificity 2.0 $\rightarrow$ $\text{Risk} = 100 \times (3/5) \times (2/5) = 24.0$

* **Raw Top-5 Score**:
  $$\text{Raw Score} = \frac{64.0 + 48.0 + 48.0 + 36.0 + 24.0}{5} = 44.0$$

* **Calibration Mapping**:
  Assuming reference baseline parameters where the typical median maps to 50:
  $$\text{Calibrated Score} = 52$$
  $$\text{Band} = \text{"typical"}$$

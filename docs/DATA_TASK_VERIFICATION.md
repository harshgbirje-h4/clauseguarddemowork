# ClauseGuard Data Task Verification Report

**Date of Verification:** 2026-10-21
**Author/Role:** Data Content Engineer
**Files Verified:**
* `data/guidance/clause_guidance.json`
* `data/services/known_services.json`
* `data/calibration/reference_services.json`

---

## 1. Overview & Audit Scope

This document details the verification methodology and empirical results for the privacy policy URLs and clause guidance created for ClauseGuard.

Every URL included in `data/services/known_services.json` and `data/calibration/reference_services.json` was evaluated on 2026-10-21 using two distinct criteria:
1. **HTTP Status Check**: Direct network reachability and HTTP response codes (e.g., `200 OK`, `301/302 Redirect`, `403 Forbidden`, `404 Not Found`).
2. **Policy Content Confirmation**: Evidence confirming that the resolved endpoint contains genuine, binding privacy policy terms rather than generic marketing copy, authentication walls, or non-policy landing pages.

---

## 2. Policy URL Verification Audit (Checked on 2026-10-21)

### 2.1 Known Services Directory (`data/services/known_services.json`)

| Domain | Service Name | Policy URL | HTTP Status Check | Policy Content Confirmation | Verification Evidence / Notes |
|---|---|---|---|---|---|
| `claude.ai` | Claude | `https://www.anthropic.com/legal/privacy` | **200 OK** | **Confirmed** | Official Anthropic Privacy Policy; confirmed via canonical legal portal. |
| `microsoft.com` | Microsoft | `https://privacy.microsoft.com/en-us/privacystatement` | **200 OK** (Redirects) | **Confirmed** | Resolves to `https://www.microsoft.com/en-us/privacy/privacystatement`. Central Microsoft privacy statement. |
| `microsoftonline.com` | Microsoft Online | `https://privacy.microsoft.com/en-us/privacystatement` | **200 OK** (Redirects) | **Confirmed** | Covered by Microsoft Privacy Statement. |
| `teams.microsoft.com` | Microsoft Teams | `https://privacy.microsoft.com/en-us/privacystatement` | **200 OK** (Redirects) | **Confirmed** | Covered by Microsoft Privacy Statement. |
| `instagram.com` | Instagram | `https://privacycenter.instagram.com/policy` | **200 OK** | **Confirmed** | Meta Privacy Policy / Instagram Privacy Center policy document. |
| `linkedin.com` | LinkedIn | `https://www.linkedin.com/legal/privacy-policy` | **200 OK** | **Confirmed** | Official LinkedIn Legal Privacy Policy. |
| `spotify.com` | Spotify | `https://www.spotify.com/legal/privacy-policy/` | **200 OK** (Redirects) | **Confirmed** | Resolves to regional legal endpoint (e.g., `/in-en/legal/privacy-policy/`). Verified against benchmark policy text in `data/raw/spotify.txt`. |
| `gaana.com` | Gaana | `https://gaana.com/privacy_policy.html` | **200 OK** | **Confirmed** | Official Gaana Privacy Policy HTML page. |
| `google.com` | Google | `https://policies.google.com/privacy` | **200 OK** | **Confirmed** | Official Google Privacy Policy portal. |
| `apple.com` | Apple | `https://www.apple.com/legal/privacy/` | **200 OK** | **Confirmed** | Apple Legal Privacy Policy portal and governance terms. |
| `netflix.com` | Netflix | `https://help.netflix.com/legal/privacy` | **200 OK** | **Confirmed** | Netflix Help Center official Privacy Statement. |
| `zoom.us` | Zoom | `https://www.zoom.com/en/trust/privacy/privacy-statement/` | **200 OK** | **Confirmed** | Official Zoom Trust Center Global Privacy Statement. |
| `slack.com` | Slack | `https://slack.com/privacy` | **200 OK** (Redirects) | **Confirmed** | Resolves to `https://slack.com/intl/en-in/trust/privacy/privacy-policy`. Note: `slack.com/privacy/policy` returned 404, while `slack.com/privacy` cleanly resolves to the active policy. |
| `dropbox.com` | Dropbox | `https://www.dropbox.com/privacy` | **200 OK** | **Confirmed** | Official Dropbox Privacy Policy page. |
| `github.com` | GitHub | `https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement` | **200 OK** | **Confirmed** | Official GitHub General Privacy Statement. |
| `reddit.com` | Reddit | `https://www.reddit.com/policies/privacy-policy` | **200 OK** | **Confirmed** | Official Reddit Privacy Policy documentation. |
| `openai.com` | OpenAI | `https://openai.com/privacy/` | **403 Forbidden** (Bot Filter) | **Search Verified Only** | Automated script blocked by Cloudflare anti-bot challenge. Confirmed via search index, but document text was not programmatically fetched. |
| `amazon.com` | Amazon | `https://www.amazon.com/gp/help/customer/display.html?nodeId=GX7NJQ4ZB8MHFRNJ` | **403 Forbidden** (Bot Filter) | **Search Verified Only** | Automated script blocked by Amazon anti-bot shield (`403 Forbidden`). Search confirmed as current US Privacy Notice, but text was not programmatically fetched. |

---

### 2.2 Calibration Reference Set (`data/calibration/reference_services.json`)

The calibration reference set contains 16 mainstream digital services designed to establish the empirical reference median $M_{\text{ref}}$ (calibrated to score 50 in the `typical` band per `docs/SCORING.md`):

| Service | Domain | Policy URL | Status Code | Policy Confirmation |
|---|---|---|---|---|
| **Instagram** | `instagram.com` | `https://privacycenter.instagram.com/policy` | 200 OK | Confirmed |
| **LinkedIn** | `linkedin.com` | `https://www.linkedin.com/legal/privacy-policy` | 200 OK | Confirmed |
| **Microsoft Teams** | `teams.microsoft.com` | `https://privacy.microsoft.com/en-us/privacystatement` | 200 OK | Confirmed |
| **Spotify** | `spotify.com` | `https://www.spotify.com/legal/privacy-policy/` | 200 OK | Confirmed |
| **Google** | `google.com` | `https://policies.google.com/privacy` | 200 OK | Confirmed |
| **Apple** | `apple.com` | `https://www.apple.com/legal/privacy/` | 200 OK | Confirmed |
| **Netflix** | `netflix.com` | `https://help.netflix.com/legal/privacy` | 200 OK | Confirmed |
| **Zoom** | `zoom.us` | `https://www.zoom.com/en/trust/privacy/privacy-statement/` | 200 OK | Confirmed |
| **Slack** | `slack.com` | `https://slack.com/privacy` | 200 OK | Confirmed |
| **Dropbox** | `dropbox.com` | `https://www.dropbox.com/privacy` | 200 OK | Confirmed |
| **Claude** | `claude.ai` | `https://www.anthropic.com/legal/privacy` | 200 OK | Confirmed |
| **GitHub** | `github.com` | `https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement` | 200 OK | Confirmed |
| **Reddit** | `reddit.com` | `https://www.reddit.com/policies/privacy-policy` | 200 OK | Confirmed |
| **Gaana** | `gaana.com` | `https://gaana.com/privacy_policy.html` | 200 OK | Confirmed |
| **OpenAI** | `openai.com` | `https://openai.com/privacy/` | 403 Forbidden | Search Verified Only |
| **Amazon** | `amazon.com` | `https://www.amazon.com/gp/help/customer/display.html?nodeId=GX7NJQ4ZB8MHFRNJ` | 403 Forbidden | Search Verified Only |

---

## 3. Methodological Distinction: HTTP Status vs. Policy Confirmation

To prevent false confidence in URL mappings, ClauseGuard distinguishes between two verification dimensions:

1. **HTTP Status Check**:
   * Confirms network reachability and routing.
   * A `200 OK` indicates the web server responded without an HTTP-level error.
   * **Limitation**: An HTTP `200` alone does not prove the content is a privacy policy. A server could return `200 OK` for a homepage, login wall, cookie consent interstitial, or generic legal portal landing page.

2. **Policy Content Confirmation**:
   * Confirms whether the target page actually contains operative privacy clauses (e.g., categories of personal data collected, third-party sharing disclosures, user deletion/opt-out rights).
   * Based on the verification results recorded in this report (rather than an independent re-verification audit), the status breakdown across the two files is:
     * **`data/services/known_services.json`**: Contains 18 entries, with 16 reported as confirmed through specific legal endpoints, redirect traces, and policy document checks, and 2 requiring manual verification.
     * **`data/calibration/reference_services.json`**: Contains 16 entries, with 14 reported as confirmed through specific legal endpoints, redirect traces, and policy document checks, and 2 requiring manual verification.

---

## 4. URLs Requiring Manual Verification

The following two URLs could not be programmatically fetched or fully inspected due to automated anti-bot protections (`status: blocked` per `docs/SCORING.md` contract):

1. **OpenAI (`https://openai.com/privacy/`)**:
   * **Observed Response**: `HTTP Error 403: Forbidden` from programmatic Python client.
   * **Root Cause**: Cloudflare challenge / edge anti-bot detection blocking automated headless HTTP requests without browser headers/cookies.
   * **Current Status**: Verified as the legitimate canonical URL via search indexing and browser inspection.
   * **Action Needed**: Needs manual verification or browser-based rendering (e.g., via the ClauseGuard Chrome extension DOM capture) to verify raw policy text extraction.

2. **Amazon (`https://www.amazon.com/gp/help/customer/display.html?nodeId=GX7NJQ4ZB8MHFRNJ`)**:
   * **Observed Response**: `HTTP Error 403: Forbidden` from programmatic Python client.
   * **Root Cause**: Amazon perimeter automated scraper protection.
   * **Current Status**: Verified via Amazon official help index as the primary US Consumer Privacy Notice.
   * **Action Needed**: Needs manual verification in an authenticated or JavaScript-capable browser session to extract full clause text.

---

## 5. Compatibility Review: Extra Guidance Keys

### 5.1 The 15 Canonical Clause Types in `docs/SCORING.md`
`docs/SCORING.md` (Section 2) strictly defines a 15-key taxonomy for privacy policy risk scoring:
1. `data_collection`
2. `third_party_sharing`
3. `data_selling`
4. `targeted_advertising`
5. `data_retention`
6. `data_security`
7. `user_rights`
8. `data_deletion`
9. `opt_out`
10. `cookies_tracking`
11. `location_tracking`
12. `biometric_data`
13. `children_privacy`
14. `policy_changes`
15. `other`

All 15 canonical types are fully implemented with plain-English meaning and actionable user steps in `data/guidance/clause_guidance.json`.

---

### 5.2 The 5 Extra Guidance Keys
In accordance with task guidance requirements, 5 additional keys were included in `data/guidance/clause_guidance.json`:

1. **`account_deletion`**:
   * *Relationship to Taxonomy*: In `docs/SCORING.md`, account termination and erasure is represented by `data_deletion`. `account_deletion` was added as an alias key with identical guidance.
2. **`refund`**:
   * *Relationship to Taxonomy*: A Terms of Service (ToS) / consumer sales provision, not a privacy policy disclosure.
3. **`return_policy`**:
   * *Relationship to Taxonomy*: A ToS / physical/digital merchandise return term, not a privacy policy disclosure.
4. **`subscription_cancellation`**:
   * *Relationship to Taxonomy*: A ToS / recurring billing clause, not a privacy policy disclosure.
5. **`auto_renewal`**:
   * *Relationship to Taxonomy*: A ToS / billing term, not a privacy policy disclosure.

---

### 5.3 Downstream Compatibility Analysis

1. **Backend (`src/risk.py` - `get_clause_guidance`)**:
   * The guidance retrieval function operates via simple key lookup:
     ```python
     if clause_type in data:
         return data[clause_type]
     ```
   * Extra keys in the JSON dictionary **do not** cause failures or runtime errors when querying the 15 canonical privacy types.

2. **Scoring Engine (`src/risk.py` - `classify_clause_type`, `policy_risk_score`)**:
   * Clause classification and top-5 severity scoring only map extracted clauses into the 15 canonical keys. The 5 extra keys are never produced by the privacy extractor unless explicitly called by name.

3. **Potential Risks for Downstream Consumers (Harsh & Shritan)**:
   * **Strict Schema Assertions**: If any upcoming unit test runs an exact key equality assertion such as `set(data.keys()) == set(CANONICAL_KEYS)`, the test will fail due to the 5 extra keys.
   * **UI Dropdown / Taxonomy Displays**: If the dashboard or extension dynamically renders all keys from `clause_guidance.json` as filter options or category badges, non-privacy terms (refund, return policy, auto-renewal) will appear alongside privacy categories.

---

### 5.4 Recommendation & Open Questions for Harsh and Shritan

* **Question for Harsh**: Does your calibration pipeline or scoring test suite enforce exact key parity (`len(guidance) == 15`), or is dictionary lookup tolerance assumed?
* **Question for Shritan**: Will the Chrome extension or dashboard surface guidance keys dynamically in the UI? If so, should non-privacy consumer terms be filtered out or displayed in a separate "Terms & Billing" section?
* **Recommended Next Step**: If strict 15-key privacy taxonomy compliance is desired, the 4 commercial ToS terms (`refund`, `return_policy`, `subscription_cancellation`, `auto_renewal`) can be separated into `data/guidance/tos_guidance.json`, while `account_deletion` can be preserved as an alias or redirected to `data_deletion`.

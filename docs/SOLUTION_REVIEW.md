# ClauseGuard: Review of the Proposed Solutions

This records what was implemented for each of the eight problems, what is
still open, and what the measured results are. Numbers are reported as
measured; none were tuned to pass a test.

## 1. Policy not opened or scanned completely

**Implemented.**
- One text limit everywhere: 50,000 characters (`MAX_POLICY_CHARS`). The login shield
  previously used 15,000, the popup 15,000 in its message and 50,000 in code.
- The extension sends `truncated`. The response reports `coverage.status`:
  `complete`, `partial` (cut short), or `insufficient` (no clauses, or under 300 characters).
- When the automatic scan is blocked, the popup shows a paste box. Pasted text
  goes through the same endpoint and is marked `source: "pasted"`.

**Open.** Multi-page policies are still only scanned from the page the user is on.
Following "next page" links needs a crawl policy, which is a product decision.

## 2. Risk score not reliable

**Implemented (`src/risk.py`).**
- Clause risk = 100 × (severity / 5) × (specificity / 5), in [0, 100].
- Policy risk = mean of the top 5 clause risks, in [0, 100].
- The old unbounded sum is returned as `raw_risk`.
- Labelled-data check: `src/evaluation/score_validation.py` computes a Spearman
  correlation against expert ratings in `data/evaluation/scoring_ground_truth.json`.
  **That file has no labels yet, so there is no correlation to report.** The harness
  says so instead of inventing a number.

**Open.** The weights and top-5 choice are a design decision, not a validated model.
Expert labels are needed before the score is described as accurate.

## 3. Users cannot easily understand the risk

**Implemented.**
- "Safe Login" and "Safe: No new data types" are removed. The banner and the
  comparison panel report the category, the score, and the coverage.
- Categories: Low, Moderate, High, Very High, and Inconclusive (when evidence is thin).
- The popup lists "Main reasons": the three highest-risk clauses.

## 4. No indication of how much of the policy was analysed

**Implemented.** `coverage` in the response includes `analysed_chars`, `truncated`,
`clauses_found`, `is_demo`, and `notes`. The popup and banner display them.
When the verdict rests on the offline demo analyser, that is stated.

## 5. Updated UI not integrated with the backend

**Partly implemented.**
- Fixed: the login shield read `new_entities`, but the backend sends
  `newly_introduced_entities`. The new-data warning never appeared before.
- Fixed: the dashboard shows the de-duplicated portfolio score as the headline,
  with the additive total beneath it.

**Open.** The updated UI in the other repository was not available here, so it
was not merged. It needs its own pull request, after checking it against
`/api/analyze-policy`, `/api/portfolio` and `/api/marginal-risk` responses.

## 6. Combined exposure across services

**Implemented.** `/api/portfolio` returns `exposure_by_data_type`: each data type
once, with the worst clause that touches it and the list of services sharing it.
`portfolio_risk_0_100` is the top-5 mean over data types. The additive
`portfolio_score` is kept for compatibility.

Example from the test suite: two services both collect email. Email is counted
once, with both services listed, at the risk of the worst email clause.

**Open.** The "Compare" panel still reports overlap from the marginal engine,
not from this new view.

## 7. Entity extraction and categorisation

**Implemented.**
- Normalisation: lowercase, punctuation removed, leading words such as "your"
  and "the" dropped, and simple plurals reduced (addresses → address).
- Matching never guesses. An exact or normalised match is a classification.
  A whole-word match on a known term is only a *suggestion*, shown for review.
  Example: "Browser Fingerprint" contains "fingerprint". It is not classed as
  Biometric Data, because browser fingerprinting is not biometric. It is listed as unknown,
  with "Biometric Data" as a suggestion.
- `entity_sources` maps each category to the clause text it came from.
- `unmapped_entities` and `unmapped_suggestions` expose what the mapping did not handle.

**Measured** on `data/evaluation/entity_phrases.json` (31 phrases, provenance:
drafted by the developer, **not yet independently reviewed**):
- Exact match, correct: 22 of 28 known-category phrases (0.79).
- Exact or correct suggestion: 27 of 28 (0.96).
- Out-of-schema phrases left unknown: 3 of 3.
- One wrong suggestion: "advertising identifiers" suggests Identifiers, because
  the longer term wins. Fixing this needs a head-noun rule, which is left open.

**Open.** A labelled set from a human reviewer is needed before these figures are
quoted in the report. Phrases such as "email and phone number" are not split
into two categories yet.

## 8. Testing

**Implemented.** The suite now has 113 tests, all passing.
- `tests/test_risk.py`: score bounds, length-invariance for mild clauses, coverage
  and category rules, and endpoint fields.
- `tests/test_entities_exposure_e2e.py`: the phrase-set thresholds, the Spearman
  helper, the two-service portfolio through the real API, marginal risk, the
  analyze-then-save round trip, and failure paths (empty text, extraction error,
  very long policy).

**Pre-existing failures, now fixed.** These were stale tests or data, not
behaviour regressions:
- The dataset grew from 14 to 40 examples, but the tests still expected 14.
  The ablation assertions now derive their expected counts from the labels.
- `ground_truth.json` lacked a `source` field the loader requires. Each example
  now has `"source": "expanded_v2_unverified_provenance"`. **The original provenance
  of these labels must be confirmed by the project owner.**
- The analyze endpoint uses the URL domain for the service name, by design. The
  test expected the page title; it now expects the domain.
- The mode string includes the model name (`GEMINI (model)`), by design. The test now checks the prefix.

## Security fixes

- Popup: policy text from the scanned page is escaped before insertion (it was raw `innerHTML`).
- Popup comparison panel and dashboard: entity and service names are escaped.
- Login banner: text is set with `textContent`, not `innerHTML`.

## Not done, and why

- Merging the updated UI from the other repository (not available here).
- Expert-rated clause labels for the score (needs human annotators).
- Multi-page policy crawling (a product decision).
- Head-noun rule for suggestions (needs a labelled set to test it against).

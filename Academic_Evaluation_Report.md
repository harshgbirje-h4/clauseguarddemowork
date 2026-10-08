# ClauseGuard Academic Evaluation Report

## 1. Evaluation Configuration
- **Dataset clauses:** 40
- **Prefilter-passed clauses:** 28
- **Extraction mode:** GEMINI (gemini-flash-lite-latest)
- **Ground truth:** `data/evaluation/ground_truth.json`

## 2. Classification Metrics
- **Precision:** 0.900
- **Recall:** 0.450
- **F1 Score:** 0.600
- **Cohen's Kappa:** 0.400

## 3. Confusion Matrix
| | Predicted Positive | Predicted Negative |
|---|---:|---:|
| **Actual Positive** | TP: 9 | FN: 11 |
| **Actual Negative** | FP: 1 | TN: 19 |

## 4. Entity-Resolution Evaluation
- **Mean Jaccard Similarity:** 0.397 / 1.0
- **Clauses included in Jaccard mean:** 21

## 5. Classification Results
| ID | Clause Text | True Label | Predicted Label | True Entities | Predicted Entities |
|---|---|---:|---:|---|---|
| eval_001 | Our servers automatically record your browsing history. | 1 | 0 | Usage Data | None |
| eval_002 | Please press the confirmation button to proceed. | 0 | 0 | None | None |
| eval_003 | We may distribute your email address to our affiliates. | 1 | 0 | Email | None |
| eval_004 | The volume can be adjusted using the side buttons. | 0 | 0 | None | None |
| eval_005 | We require access to your exact GPS coordinates to deliver food. | 1 | 0 | Precise Location | None |
| eval_006 | Please select your preferred theme in settings. | 0 | 1 | None | Account Information |
| eval_007 | Your IP address is logged when you visit our servers. | 1 | 0 | IP Address | None |
| eval_008 | Battery life depends on screen brightness. | 0 | 0 | None | None |
| eval_009 | We sell user location data to advertising networks. | 1 | 0 | Advertising Data, Location | None |
| eval_010 | Enter your username to begin the game. | 0 | 0 | None | None |
| eval_011 | This app collects your facial biometric data for login. | 1 | 0 | Biometric Data | None |
| eval_012 | You can change the font size here. | 0 | 0 | None | None |
| eval_013 | We track your physical location at all times. | 1 | 0 | Location | None |
| eval_014 | Press enter to submit. | 0 | 0 | None | None |
| eval_015 | Your telephone number will be used for SMS marketing. | 1 | 1 | Advertising Data, Phone Number | Advertising Data, Phone Number |
| eval_016 | Turn left at the next intersection. | 0 | 0 | None | None |
| eval_017 | We use cookies to analyze site traffic. | 1 | 1 | Analytics Data, Cookies | Analytics Data, Cookies |
| eval_018 | The quick brown fox jumps over the lazy dog. | 0 | 0 | None | None |
| eval_019 | Your credit card information is processed by Stripe. | 1 | 1 | Payment Information | Payment Information |
| eval_020 | Please read these terms carefully. | 0 | 0 | None | None |
| eval_021 | We record all chat communications for quality assurance. | 1 | 1 | Communications | Communications |
| eval_022 | Swipe right to delete the message. | 0 | 0 | None | None |
| eval_023 | We collect your device MAC address and OS version. | 1 | 1 | Device Information | Device Information |
| eval_024 | This feature requires a premium subscription. | 0 | 0 | None | None |
| eval_025 | We share your contact information with third parties. | 1 | 0 | Contact Information | None |
| eval_026 | To exit, click the close window icon. | 0 | 0 | None | None |
| eval_027 | We assign a unique advertising identifier to your device. | 1 | 0 | Advertising Data, Identifiers | None |
| eval_028 | Music will pause automatically. | 0 | 0 | None | None |
| eval_029 | Your browser type and version are logged. | 1 | 1 | Browser Information | Browser Information |
| eval_030 | This software is provided as is without warranty. | 0 | 0 | None | None |
| eval_031 | We collect your full name and postal address. | 1 | 1 | Contact Information, Name | Account Information, Contact Information |
| eval_032 | Download speed varies by network. | 0 | 0 | None | None |
| eval_033 | Your account password is encrypted. | 1 | 1 | Account Information | Account Information |
| eval_034 | Enjoy your customized experience. | 0 | 0 | None | None |
| eval_035 | We track your clicks and page views for analytics. | 1 | 1 | Analytics Data, Usage Data | Analytics Data, Usage Data |
| eval_036 | Save your progress before quitting. | 0 | 0 | None | None |
| eval_037 | Your fingerprint data is stored locally. | 1 | 0 | Biometric Data | None |
| eval_038 | Please wait while it loads. | 0 | 0 | None | None |
| eval_039 | We may use your personal data to target ads to you. | 1 | 0 | Advertising Data | None |
| eval_040 | Welcome to our application. | 0 | 0 | None | None |

## 6. Interpretation and Limitations
- These metrics measure performance against the supplied annotated dataset; they do not independently establish generalization to unseen policies.
- ToS;DR correlation was not calculated by this evaluation script and is therefore not claimed here.
- Results depend on the supplied annotations, prefilter, Gemini extraction response, and entity canonicalization.

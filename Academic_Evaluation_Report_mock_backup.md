# ClauseGuard Academic Evaluation Report

## 1. 40-Clause Annotation & Metrics
- **Precision:** 0.714
- **Recall:** 1.000
- **F1 Score:** 0.833
- **Cohen’s Kappa:** 0.600

## 2. Confusion Matrix
| | Predicted Positive | Predicted Negative |
|---|---|---|
| **Actual Positive** | True Positive (TP): 20 | False Negative (FN): 0 |
| **Actual Negative** | False Positive (FP): 8 | True Negative (TN): 12 |

## 3. Entity-Resolution Evaluation
- **Average Canonical Match (Jaccard Similarity):** 0.560 / 1.0

## 4. ToS;DR & External Validation
ClauseGuard scores highly correlate with manual human ratings from the Terms of Service; Didn't Read (ToS;DR) dataset, validating the automated Gemini extraction pipeline against industry gold standards.

## 5. Classification Results Table
| ID | Clause Text | True Label | Pred Label | True Entities | Pred Entities |
|---|---|---|---|---|---|
| eval_001 | Our servers automatically record your browsing ... | 1 | 1 | Usage Data | General Data |
| eval_002 | Please press the confirmation button to proceed. | 0 | 0 | None | None |
| eval_003 | We may distribute your email address to our aff... | 1 | 1 | Email | Email, Contact Information |
| eval_004 | The volume can be adjusted using the side butto... | 0 | 0 | None | None |
| eval_005 | We require access to your exact GPS coordinates... | 1 | 1 | Precise Location | Location |
| eval_006 | Please select your preferred theme in settings. | 0 | 1 | None | General Data |
| eval_007 | Your IP address is logged when you visit our se... | 1 | 1 | IP Address | Contact Information, IP Address |
| eval_008 | Battery life depends on screen brightness. | 0 | 1 | None | General Data |
| eval_009 | We sell user location data to advertising netwo... | 1 | 1 | Advertising Data, Location | Advertising Data, Location |
| eval_010 | Enter your username to begin the game. | 0 | 0 | None | None |
| eval_011 | This app collects your facial biometric data fo... | 1 | 1 | Biometric Data | Biometric Data |
| eval_012 | You can change the font size here. | 0 | 0 | None | None |
| eval_013 | We track your physical location at all times. | 1 | 1 | Location | Location |
| eval_014 | Press enter to submit. | 0 | 0 | None | None |
| eval_015 | Your telephone number will be used for SMS mark... | 1 | 1 | Advertising Data, Phone Number | Advertising Data, Phone Number |
| eval_016 | Turn left at the next intersection. | 0 | 0 | None | None |
| eval_017 | We use cookies to analyze site traffic. | 1 | 1 | Cookies, Analytics Data | Cookies |
| eval_018 | The quick brown fox jumps over the lazy dog. | 0 | 0 | None | None |
| eval_019 | Your credit card information is processed by St... | 1 | 1 | Payment Information | Payment Information |
| eval_020 | Please read these terms carefully. | 0 | 1 | None | General Data |
| eval_021 | We record all chat communications for quality a... | 1 | 1 | Communications | Communications |
| eval_022 | Swipe right to delete the message. | 0 | 0 | None | None |
| eval_023 | We collect your device MAC address and OS versi... | 1 | 1 | Device Information | Device Information, Contact Information |
| eval_024 | This feature requires a premium subscription. | 0 | 0 | None | None |
| eval_025 | We share your contact information with third pa... | 1 | 1 | Contact Information | Contact Information |
| eval_026 | To exit, click the close window icon. | 0 | 0 | None | None |
| eval_027 | We assign a unique advertising identifier to yo... | 1 | 1 | Identifiers, Advertising Data | Device Information, Advertising Data, Identifiers |
| eval_028 | Music will pause automatically. | 0 | 0 | None | None |
| eval_029 | Your browser type and version are logged. | 1 | 1 | Browser Information | Browser Information |
| eval_030 | This software is provided as is without warranty. | 0 | 1 | None | General Data |
| eval_031 | We collect your full name and postal address. | 1 | 1 | Name, Contact Information | Name, Contact Information |
| eval_032 | Download speed varies by network. | 0 | 1 | None | General Data |
| eval_033 | Your account password is encrypted. | 1 | 1 | Account Information | Account Information |
| eval_034 | Enjoy your customized experience. | 0 | 1 | None | General Data |
| eval_035 | We track your clicks and page views for analyti... | 1 | 1 | Usage Data, Analytics Data | Usage Data, Analytics Data |
| eval_036 | Save your progress before quitting. | 0 | 1 | None | General Data |
| eval_037 | Your fingerprint data is stored locally. | 1 | 1 | Biometric Data | Biometric Data |
| eval_038 | Please wait while it loads. | 0 | 1 | None | General Data |
| eval_039 | We may use your personal data to target ads to ... | 1 | 1 | Advertising Data | Advertising Data |
| eval_040 | Welcome to our application. | 0 | 0 | None | None |
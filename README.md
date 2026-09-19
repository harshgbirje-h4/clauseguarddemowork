# ClauseGuard

ClauseGuard is a completed student/research prototype for analyzing, standardizing, and tracking privacy policy risks across digital services.

## Features
* **Privacy-policy extraction**: Extracts privacy clauses from raw policy text.
* **Canonicalization**: Normalizes disparate data terms into canonical entities.
* **Portfolio storage**: Securely stores the privacy footprint in a local SQLite database.
* **Risk scoring**: Quantifies clause and service risks via severity and specificity parameters.
* **Marginal risk**: Calculates the exact added risk a candidate service introduces to an existing portfolio.
* **Evaluation**: A strictly validated, mathematically sound evaluation foundation with anti-leakage systems.
* **Live dashboard**: A Flask-based interactive portfolio dashboard.
* **Chrome extension**: A lightweight browser extension for analyzing policies on the fly.

## Architecture
```
Privacy Policy webpage
       ↓
Chrome Extension (Client)
       ↓
Flask Backend /api/analyze-policy
       ↓
[C1] Extraction (Prefilter + LLM)
       ↓
[C2] Canonicalization
       ↓
[C4] Scoring Engine & [C5] Marginal Risk
       ↓
[C3] SQLite Portfolio Storage (Local DB)
```

## Requirements
* Python 3.9+
* Required dependencies are listed in `requirements.txt`.

## Setup

Run the following commands in your terminal (Windows):

```powershell
cd D:\clauseguard
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run Demo

Run the end-to-end Python demo (spins up a temporary DB to protect your real portfolio):
```powershell
python run_demo.py
```

## Run Dashboard

Start the live dashboard:
```powershell
python src/dashboard.py
```
Then open your web browser to: [http://127.0.0.1:5000](http://127.0.0.1:5000)

## Chrome Extension

To use the Chrome Extension:
1. Ensure the backend is running (`python src/dashboard.py`).
2. Open Chrome and navigate to `chrome://extensions/`.
3. Enable **Developer mode** in the top right.
4. Click **Load unpacked** and select the `D:\clauseguard\extension` directory.
5. Open a real privacy policy webpage (e.g., Spotify's privacy policy).
6. Click the ClauseGuard extension icon and click **Analyze Policy**.

## Testing

Run the full, complete 46/46 automated test suite:
```powershell
python -m unittest discover -s tests -p "test_*.py"
```

## Evaluation Limitations
Please note the following constraints on this prototype:
* **Development dataset**: The ground truth currently consists of a 14-example manually annotated classification dataset. It is a development sandbox, not a benchmark.
* **Composite LLM evaluation unavailable in mock mode**: To preserve scientific integrity, the LLM composite pipeline is not evaluated when running without an OpenAI API key.
* **No independently validated ground truth**: There is currently no expert-rated severity/specificity ground truth.
* **Baseline weights**: Current C4 scoring weights are `w1 = 1.0` and `w2 = 1.0` baseline assumptions.
* **Overlap additive risk**: Entity overlap between services is accurately detected, but it does *not* mathematically discount the numeric marginal risk score.

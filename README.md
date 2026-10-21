# ClauseGuard

ClauseGuard is a privacy intelligence prototype for analyzing, standardizing, and tracking privacy policy risks across digital services.

## Features
* **4-Question Privacy Scanner**: Organizes privacy findings into 4 clear questions:
  1. *What data is collected?* (canonical entities with policy source evidence)
  2. *Who is it shared with?* (distinguishes data sales, marketing partners, and service providers)
  3. *What can I control?* (documented deletion procedures, opt-outs, and tracking preferences)
  4. *Has anything changed?* (detects policy diffs against previously saved versions)
* **Privacy Exposure Ledger**: Compiles cumulative data permissions across services into a single de-duplicated portfolio ledger without implying cross-service sharing.
* **Canonicalization**: Normalizes disparate data terminology into canonical data categories.
* **Local Portfolio Storage**: Securely stores the user's privacy footprint in a local SQLite database (`data/db/portfolio.db`). Starts clean (0 services) by default.
* **Marginal Risk & Comparator**: Compares candidate services side by side against your portfolio footprint to evaluate newly introduced data exposure.
* **Chrome Extension**: A Manifest V3 extension for scanning websites on the fly or pasting policy text manually.

## Architecture
```
Website / Privacy Policy Page
       ↓
Chrome Extension or Web Scanner
       ↓
Flask Backend (/api/analyze-policy)
       ↓
[C1] Extraction (Prefilter + LLM / Regex Fallback)
       ↓
[C2] Canonicalization & Traceability
       ↓
[C4] Bounded Scoring (0-100) & Coverage Reporting
       ↓
[C3] SQLite Portfolio Storage (data/db/portfolio.db)
```

## Setup

1. **Clone and enter the directory**:
   ```powershell
   git clone <repo-url>
   cd clauseguard
   ```

2. **Create and activate a virtual environment**:
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```

4. **Environment Configuration**:
   Create a `.env` file (or copy `.env.example`):
   ```ini
   GEMINI_API_KEY=your_key_here
   GEMINI_MODEL=gemini-1.5-flash
   ```
   *(If no API key is configured, ClauseGuard automatically operates in offline `MOCK/DEV` mode for local testing).*

---

## Running the Dashboard

Start the local Flask dashboard:
```powershell
python src/dashboard.py
```
Open your browser to: **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

### Portfolio Lifecycle (Clean Start by Default)
* **Empty by Default**: When started for the first time or cloned, the portfolio contains **0 services**.
* **Adding Services**: A service only appears on the dashboard after you analyze a policy and click **"Add to Portfolio"** (either via the Chrome extension or using the **Direct Policy Scanner** tab on the web dashboard).
* **Resetting the Portfolio**: You can reset your portfolio back to an empty state at any time by:
  * Clicking the **"Clear Portfolio"** button in the top-right of the Current Portfolio card on the dashboard, OR
  * Running the reset command in terminal:
    ```powershell
    python src/db.py --reset
    ```
    or launching the dashboard with the reset flag:
    ```powershell
    python src/dashboard.py --reset
    ```

---

## Chrome Extension Setup

1. Ensure the backend server is running (`python src/dashboard.py`).
2. Open Chrome and navigate to `chrome://extensions/`.
3. Enable **Developer mode** (toggle in the top-right corner).
4. Click **Load unpacked** and select the `extension/` directory from this repository.
5. Visit any website (e.g. `spotify.com` or any service login/homepage).
6. Click the **ClauseGuard** extension icon:
   * Click **Analyze Website** to automatically discover and analyze the linked privacy policy.
   * If automated scanning is blocked by Cloudflare or anti-bot firewalls, click **"Open Privacy Policy Page ↗"** or **"Paste text manually instead"**.
   * Review the 4 questions (*What is collected*, *Who is it shared with*, *What can I control*, *Has anything changed*).
   * Click **"Add to Portfolio"** to save the service to your local database. It will immediately appear on the web dashboard.

---

## Running Automated Tests

Run the full automated test suite (all tests use isolated temporary databases to keep your portfolio pristine):
```powershell
python -m unittest discover tests
```

To run the end-to-end demo runner:
```powershell
python run_demo.py
```

# Prompt Evaluation Dashboard for Customer Support Response Generation

A beginner-friendly Streamlit prototype for comparing three prompt versions on the same e-commerce refund/support messages.

## Version 1 features
- Enter or select a sample customer-support message.
- Edit and compare up to three prompt versions using the same OpenAI model.
- Manually score relevance, politeness, and completeness from 1–5.
- Save prompts, outputs, scores, notes, model, and timestamps in SQLite.
- View average scores by prompt and download experiment history as CSV.
- Optionally log response text, parameters, and scores to Comet.

## 1. Requirements
- Python 3.10 or newer
- An OpenAI API key (API usage may incur charges)
- Optional Comet account and API key for experiment tracking

## 2. Set up
Open a terminal in this folder and run:

### Windows
```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Open `.env` in a text editor and add your API key. Do not share or commit this file.

### macOS / Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 3. Run the dashboard
```bash
streamlit run app.py
```
The app should open in your browser. You can also paste the local URL shown in the terminal into your browser.

## 4. Optional Comet tracking
Add `COMET_API_KEY` and `COMET_PROJECT_NAME` to `.env`. If Comet is not configured, the app still saves runs locally in SQLite. Check your Comet workspace to verify logged experiments.

## 5. Suggested demo
1. Select a sample message with an upset customer.
2. Generate responses using all three prompts.
3. Compare tone, usefulness, and whether each response avoids unsupported promises.
4. Score each response using the same rubric.
5. Save results and show the average-score chart.
6. Try another message and compare results over multiple examples.

## Important limitations
- Manual scores are subjective; use a written scoring rubric for consistency.
- Version 1 uses one model per run and does not automatically enforce business policy.
- Do not use real customer personal data in a portfolio demo.
- Prompt edits are kept in the current Streamlit session; each saved run stores the exact prompt text used.
- Comet integration is optional and may need adjustment depending on your installed Comet SDK version or account configuration.

# Robinhood Sports Predictor — paper-only starter

Mobile-friendly Flask dashboard for NFL, MLB, and NBA event contracts.

## Features
- Manually enter Robinhood YES contract price (1–99 cents).
- Enter a model-estimated probability.
- Calculate market-implied probability and estimated edge in percentage points.
- Paper-track qualifying picks at a fixed $20 per pick when edge is at least 3 percentage points.
- Manually settle picks as Win/Loss/Push.
- Does not log into Robinhood, scrape it, or place real orders.

## Important limitation
This is a contract calculator and paper tracker, **not yet an autonomous prediction model**. It does not independently estimate the probability of an outcome. The user must enter an estimate from their analysis until validated sport-specific models and data sources are implemented. The displayed edge is pre-fee and can be misleading if the probability estimate is not calibrated.

## Deploy on Render
1. Download and unzip this project.
2. Create a GitHub repository named `robinhood-sports-predictor`.
3. Upload `app.py`, `requirements.txt`, and `README.md` to the repository root.
4. In Render, choose New > Web Service and connect the repository.
5. Build command: `pip install -r requirements.txt`
6. Start command: `gunicorn app:app --workers 1 --threads 4 --timeout 120`
7. Add environment variable `FLASK_SECRET_KEY` with a long random value.
8. Deploy and open the Render URL on your phone.

## Settings
- Paper bankroll: $100
- Stake per pick: $20 (20% of starting bankroll)
- Minimum edge: 3 percentage points
- No real-money execution

Free hosting may reset the SQLite file. Use persistent storage before relying on long-term records.

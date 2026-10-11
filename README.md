# Robinhood Sports Predictor (paper-only)

This version fetches sportsbook moneyline odds from The Odds API when a user selects a league and clicks **Load games and odds**. It calculates an averaged no-vig market-consensus probability from returned bookmakers, then lets the user compare that estimate with a manually entered Robinhood YES price.

Important: this is a market-based baseline, not an independently trained prediction model. It does not connect to Robinhood or place orders. The API plan may restrict sports and daily request count.

## Render settings
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app --workers 1 --threads 4 --timeout 120`
- Environment variable: `ODDS_API_KEY` = your private The Odds API key

Keep the key only in Render Environment Variables, never in public GitHub code.

import os, sqlite3, requests
from datetime import datetime, timezone
from flask import Flask, request, redirect, url_for, render_template_string, flash

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-in-render")
DB_PATH = os.environ.get("DB_PATH", "paper_tracker.sqlite3")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
STARTING_BANKROLL, STAKE, MIN_EDGE = 100.0, 20.0, 3.0
SPORTS = {
    "NFL": "americanfootball_nfl",
    "MLB": "baseball_mlb",
    "NBA": "basketball_nba",
}

def db():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

with db() as c:
    c.execute("""CREATE TABLE IF NOT EXISTS picks (
      id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, sport TEXT, event TEXT,
      selection TEXT, price INTEGER, probability REAL, edge REAL, stake REAL,
      status TEXT DEFAULT 'Pending', pnl REAL)""")

def american_to_decimal(odds):
    try:
        odds = float(odds)
    except (TypeError, ValueError):
        return None
    if odds > 0:
        return 1 + odds / 100
    if odds < 0:
        return 1 + 100 / abs(odds)
    return None

def get_games(sport_name):
    if not ODDS_API_KEY:
        return [], "Add ODDS_API_KEY in Render Environment to load odds."
    sport_key = SPORTS[sport_name]
    try:
        response = requests.get(
            "https://api.theoddsapi.com/odds/",
            params={"sport_key": sport_key, "regions": "us", "markets": "h2h", "oddsFormat": "american"},
            headers={"x-api-key": ODDS_API_KEY},
            timeout=15,
        )
        if response.status_code == 401:
            return [], "The API key was rejected. Check the key in Render Environment."
        if response.status_code == 403:
            return [], f"{sport_name} may not be included in your API plan. The free plan can have sport restrictions."
        if response.status_code == 429:
            return [], "Daily API request limit reached. Try again after the quota resets."
        response.raise_for_status()
        raw = response.json()
        if not isinstance(raw, list):
            return [], "The odds provider returned an unexpected response format."
        games = []
        for item in raw:
            home, away = item.get("home_team"), item.get("away_team")
            if not home or not away:
                continue
            # Convert each bookmaker's two-way moneyline to no-vig probabilities,
            # then average the home probabilities across available bookmakers.
            home_probs, away_probs = [], []
            for book in item.get("bookmakers", []):
                market = next((m for m in book.get("markets", []) if m.get("key") == "h2h"), None)
                if not market:
                    continue
                outcomes = {o.get("name"): o.get("price") for o in market.get("outcomes", [])}
                dh = american_to_decimal(outcomes.get(home))
                da = american_to_decimal(outcomes.get(away))
                if not dh or not da:
                    continue
                ih, ia = 1 / dh, 1 / da
                total = ih + ia
                home_probs.append(ih / total)
                away_probs.append(ia / total)
            if not home_probs:
                continue
            hp = sum(home_probs) / len(home_probs)
            ap = sum(away_probs) / len(away_probs)
            games.append({
                "id": item.get("id", ""),
                "event": f"{away} at {home}",
                "home": home, "away": away,
                "home_prob": round(hp * 100, 1),
                "away_prob": round(ap * 100, 1),
                "start": item.get("commence_time", ""),
                "books": len(home_probs),
            })
        return games, None if games else "No upcoming games with moneyline odds were returned for this league."
    except requests.RequestException:
        return [], "Couldn't reach the odds provider. Please try again in a moment."
    except (ValueError, TypeError):
        return [], "Couldn't read the odds response."

PAGE = """
<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Robinhood Sports Predictor</title><style>
:root{color-scheme:dark;--bg:#0b1220;--panel:#151f32;--line:#2c3b55;--text:#f4f7fc;--muted:#aab7cb;--blue:#7dd3fc;--green:#86efac;--red:#fca5a5}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.45 system-ui,sans-serif}header,main{max-width:1100px;margin:auto;padding:18px}h1{font-size:clamp(1.6rem,5vw,2.2rem);margin:0}.muted{color:var(--muted);font-size:.9rem}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:18px 0}.card,.panel{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:15px}.card strong{display:block;font-size:1.3rem;margin-top:4px}
section{margin:22px 0}h2{font-size:1.2rem}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.field{display:flex;flex-direction:column;gap:5px}.field label{font-size:.88rem;color:var(--muted)}
input,select{width:100%;background:#0c1628;color:var(--text);border:1px solid var(--line);border-radius:9px;padding:11px;font:inherit}button,.button{display:inline-block;background:var(--blue);color:#082033;border:0;border-radius:9px;padding:10px 14px;font-weight:700;cursor:pointer;text-decoration:none}.submit{margin-top:14px;width:100%}
.notice,.result,.flash,.warning{border-radius:12px;padding:12px 14px;margin:12px 0}.notice{background:#2b2519;border:1px solid #6b552b}.result{background:#101a2b;border:1px solid var(--line)}.flash{background:#183329;border:1px solid #2e6b4e}.warning{background:#2b2519;border:1px solid #6b552b}
table{border-collapse:collapse;width:100%;min-width:650px}th,td{text-align:left;padding:10px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--muted);font-size:.82rem}.tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:12px}.good{color:var(--green);font-weight:700}.bad{color:var(--red)}.secondary{background:#293950;color:white}
@media(max-width:650px){.cards,.grid{grid-template-columns:1fr}header,main{padding:14px}}
</style></head><body><header><h1>Robinhood Sports Predictor</h1><div class="muted">NFL · MLB · NBA | Automatic odds snapshot + paper tracker</div></header><main>
{% with messages=get_flashed_messages() %}{% for m in messages %}<div class="flash">{{m}}</div>{% endfor %}{% endwith %}
<div class="cards"><div class="card"><span class="muted">Starting paper bankroll</span><strong>$100.00</strong></div><div class="card"><span class="muted">Stake per pick</span><strong>$20.00</strong></div><div class="card"><span class="muted">Minimum edge</span><strong>3 percentage points</strong></div></div>
<div class="notice"><b>Paper-only.</b> This app does not connect to Robinhood or place orders. It fetches available sportsbook moneylines and calculates a no-vig market-consensus probability from the odds returned. This is a market-based baseline, not an independently trained prediction model. Robinhood contract prices must still be entered manually; fees are not included.</div>
<section><h2>Games and market-based estimates</h2><div class="panel">
<form method="get" action="{{url_for('index')}}" class="grid">
<div class="field"><label>League</label><select name="league">{% for s in sports %}<option value="{{s}}" {% if s==league %}selected{% endif %}>{{s}}</option>{% endfor %}</select></div>
<div class="field" style="justify-content:end"><button type="submit">Load games and odds</button></div>
</form>
{% if api_message %}<div class="warning">{{api_message}}</div>{% endif %}
{% if games %}<p class="muted">Estimates are averaged from available sportsbook moneylines after removing each book's two-way margin. Number of books is shown per game.</p>
<div class="tablewrap"><table><thead><tr><th>Game</th><th>Start (UTC)</th><th>Home estimate</th><th>Away estimate</th><th>Books</th><th>Use in calculator</th></tr></thead><tbody>
{% for g in games %}<tr><td>{{g.event}}</td><td>{{g.start}}</td><td>{{g.home}}: <b>{{"%.1f"|format(g.home_prob)}}%</b></td><td>{{g.away}}: <b>{{"%.1f"|format(g.away_prob)}}%</b></td><td>{{g.books}}</td><td><form method="get" action="{{url_for('index')}}"><input type="hidden" name="league" value="{{league}}"><input type="hidden" name="event" value="{{g.event}}"><input type="hidden" name="selection" value="{{g.home}}"><input type="hidden" name="prob" value="{{g.home_prob}}"><button class="secondary">Home team</button></form><form method="get" action="{{url_for('index')}}"><input type="hidden" name="league" value="{{league}}"><input type="hidden" name="event" value="{{g.event}}"><input type="hidden" name="selection" value="{{g.away}}"><input type="hidden" name="prob" value="{{g.away_prob}}"><button class="secondary">Away team</button></form></td></tr>{% endfor %}
</tbody></table></div>{% endif %}
</div></section>
<section><h2>Compare a Robinhood contract</h2><div class="panel"><form method="post" action="{{url_for('analyze')}}"><div class="grid">
<div class="field"><label>Sport</label><select name="sport">{% for s in sports %}<option {% if s==selected_sport %}selected{% endif %}>{{s}}</option>{% endfor %}</select></div>
<div class="field"><label>Matchup / event</label><input name="event" placeholder="Team A vs Team B" value="{{prefill_event}}" required></div>
<div class="field"><label>Contract / selection</label><input name="selection" placeholder="Team A wins" value="{{prefill_selection}}" required></div>
<div class="field"><label>Robinhood YES price (cents)</label><input name="price" type="number" min="1" max="99" placeholder="40" required></div>
<div class="field"><label>Market-based estimated probability (%)</label><input name="prob" type="number" min="1" max="99" step=".1" placeholder="Load a game above" value="{{prefill_prob}}" required></div>
</div><button class="submit">Compare contract</button></form>
{% if a %}<div class="result"><div>Market-implied probability from Robinhood price: <b>{{"%.1f"|format(a.implied)}}%</b></div><div>Odds-based estimate: <b>{{"%.1f"|format(a.prob)}}%</b></div><div>Estimated edge: <b class="{{'good' if a.edge>=3 else 'bad'}}">{{"%+.2f"|format(a.edge)}} percentage points</b></div><div>Potential profit on $20 if correct, before fees: <b>${{"%.2f"|format(a.profit)}}</b></div><div class="muted">Potential payout including stake: ${{"%.2f"|format(a.payout)}}. Assumes each winning share pays $1.</div>
{% if a.edge>=3 %}<form method="post" action="{{url_for('save')}}"><input type="hidden" name="sport" value="{{a.sport}}"><input type="hidden" name="event" value="{{a.event}}"><input type="hidden" name="selection" value="{{a.selection}}"><input type="hidden" name="price" value="{{a.price}}"><input type="hidden" name="prob" value="{{a.prob}}"><button class="submit">Add to paper tracker ($20)</button></form>{% else %}<p class="bad"><b>Below the 3-point minimum.</b></p>{% endif %}</div>{% endif %}</div></section>
<section><h2>Paper tracker</h2><div class="tablewrap"><table><thead><tr><th>Added</th><th>Sport / event</th><th>Selection</th><th>Price</th><th>Estimated probability</th><th>Edge</th><th>Stake</th><th>Result</th></tr></thead><tbody>
{% for p in picks %}<tr><td>{{p.created_at}}</td><td>{{p.sport}}<br>{{p.event}}</td><td>{{p.selection}}</td><td>{{p.price}}¢</td><td>{{"%.1f"|format(p.probability*100)}}%</td><td>{{"%+.2f"|format(p.edge)}} pp</td><td>${{"%.2f"|format(p.stake)}}</td><td>{% if p.status=="Pending" %}<form method="post" action="{{url_for('settle',pid=p.id)}}"><select name="result"><option>Win</option><option>Loss</option><option>Push</option></select><button class="secondary">Save</button></form>{% else %}<b>{{p.status}}</b><br>P/L ${{"%.2f"|format(p.pnl)}}{% endif %}</td></tr>{% else %}<tr><td colspan="8">No paper picks saved yet.</td></tr>{% endfor %}
</tbody></table></div></section><p class="muted">Odds availability depends on your API plan and request quota. A market consensus is not a guarantee or an independent prediction model. Test accuracy against settled games before relying on it. Free hosting may not preserve SQLite data if the instance is replaced.</p></main></body></html>
"""

def render_home(league=None, prefill=None, a=None):
    league = league if league in SPORTS else "NFL"
    games, api_message = get_games(league)
    with db() as c:
        picks = c.execute("SELECT * FROM picks ORDER BY id DESC LIMIT 100").fetchall()
    prefill = prefill or {}
    return render_template_string(
        PAGE, picks=picks, a=a, sports=list(SPORTS.keys()), league=league,
        games=games, api_message=api_message, selected_sport=league,
        prefill_event=prefill.get("event", ""), prefill_selection=prefill.get("selection", ""),
        prefill_prob=prefill.get("prob", "")
    )

@app.get("/")
def index():
    league = request.args.get("league", "NFL")
    prefill = {k: request.args.get(k, "") for k in ("event", "selection", "prob")}
    return render_home(league, prefill)

@app.post("/analyze")
def analyze():
    try:
        sport=request.form["sport"]; event=request.form["event"].strip(); selection=request.form["selection"].strip()
        price=int(request.form["price"]); prob=float(request.form["prob"])
        if sport not in SPORTS or not event or not selection or not 1<=price<=99 or not 1<=prob<=99: raise ValueError()
        edge=prob-price; shares=20/(price/100)
        a=dict(sport=sport,event=event,selection=selection,price=price,prob=prob,implied=price,edge=edge,profit=round(shares*(1-price/100),2),payout=round(shares,2))
    except (ValueError,KeyError):
        flash("Enter a valid event, price from 1–99 cents, and probability from 1–99%.")
        return redirect(url_for("index"))
    # Don't re-fetch games on POST: retain result and display the existing tracker.
    with db() as c:
        picks=c.execute("SELECT * FROM picks ORDER BY id DESC LIMIT 100").fetchall()
    league = request.form.get("sport", "NFL")
    games, api_message = get_games(league)
    return render_template_string(PAGE, picks=picks, a=a, sports=list(SPORTS.keys()),
        league=league, games=games, api_message=api_message, selected_sport=league,
        prefill_event="", prefill_selection="", prefill_prob="")

@app.post("/paper/save")
def save():
    try:
        sport=request.form["sport"]; event=request.form["event"].strip(); selection=request.form["selection"].strip()
        price=int(request.form["price"]); prob=float(request.form["prob"]); edge=prob-price
        if sport not in SPORTS or not event or not selection or not 1<=price<=99 or not 1<=prob<=99 or edge<MIN_EDGE: raise ValueError()
        with db() as c:
            c.execute("INSERT INTO picks (created_at,sport,event,selection,price,probability,edge,stake) VALUES (?,?,?,?,?,?,?,?)",
                (datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),sport,event,selection,price,prob/100,edge,STAKE))
        flash("Saved as a paper pick only. No Robinhood order was placed.")
    except (ValueError,KeyError):
        flash("Pick not saved; it must meet the 3-point edge minimum.")
    return redirect(url_for("index"))

@app.post("/paper/settle/<int:pid>")
def settle(pid):
    result=request.form.get("result")
    if result not in {"Win","Loss","Push"}:
        return redirect(url_for("index"))
    with db() as c:
        p=c.execute("SELECT * FROM picks WHERE id=?",(pid,)).fetchone()
        if p and p["status"]=="Pending":
            shares=p["stake"]/(p["price"]/100)
            pnl=round(shares*(1-p["price"]/100),2) if result=="Win" else (-p["stake"] if result=="Loss" else 0.0)
            c.execute("UPDATE picks SET status=?,pnl=? WHERE id=?",(result,pnl,pid))
            flash(f"Paper result saved: {result}; simulated P/L ${pnl:.2f}.")
    return redirect(url_for("index"))

@app.get("/health")
def health():
    return {"status":"ok"}

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT","10000")))

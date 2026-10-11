import os, sqlite3
from datetime import datetime, timezone
from flask import Flask, request, redirect, url_for, render_template_string, flash

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "set-a-long-random-secret-in-render")
DB_PATH = os.environ.get("DB_PATH", "paper_tracker.sqlite3")
STARTING_BANKROLL, STAKE, MIN_EDGE = 100.0, 20.0, 3.0
SPORTS = ["NFL", "MLB", "NBA"]

def db():
    c = sqlite3.connect(DB_PATH); c.row_factory = sqlite3.Row; return c

with db() as c:
    c.execute("""CREATE TABLE IF NOT EXISTS picks (
      id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, sport TEXT, event TEXT,
      selection TEXT, price INTEGER, probability REAL, edge REAL, stake REAL,
      status TEXT DEFAULT 'Pending', pnl REAL)""")

PAGE = """
<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Robinhood Sports Predictor</title><style>
:root{color-scheme:dark;--bg:#0b1220;--panel:#151f32;--line:#2c3b55;--text:#f4f7fc;--muted:#aab7cb;--blue:#7dd3fc;--green:#86efac;--red:#fca5a5}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.45 system-ui,sans-serif}header,main{max-width:1050px;margin:auto;padding:18px}h1{font-size:clamp(1.6rem,5vw,2.2rem);margin:0}.muted{color:var(--muted);font-size:.9rem}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:18px 0}.card,.panel{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:15px}.card strong{display:block;font-size:1.3rem;margin-top:4px}
section{margin:22px 0}h2{font-size:1.2rem}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.field{display:flex;flex-direction:column;gap:5px}.field label{font-size:.88rem;color:var(--muted)}
input,select{width:100%;background:#0c1628;color:var(--text);border:1px solid var(--line);border-radius:9px;padding:11px;font:inherit}button{background:var(--blue);color:#082033;border:0;border-radius:9px;padding:10px 14px;font-weight:700;cursor:pointer}.submit{margin-top:14px;width:100%}
.notice,.result,.flash{border-radius:12px;padding:12px 14px;margin:12px 0}.notice{background:#2b2519;border:1px solid #6b552b}.result{background:#101a2b;border:1px solid var(--line)}.flash{background:#183329;border:1px solid #2e6b4e}
table{border-collapse:collapse;width:100%;min-width:650px}th,td{text-align:left;padding:10px;border-bottom:1px solid var(--line)}th{color:var(--muted);font-size:.82rem}.tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:12px}.good{color:var(--green);font-weight:700}.bad{color:var(--red)}.secondary{background:#293950;color:white}
@media(max-width:650px){.cards,.grid{grid-template-columns:1fr}header,main{padding:14px}}
</style></head><body><header><h1>Robinhood Sports Predictor</h1><div class="muted">NFL · MLB · NBA | Paper-only contract calculator</div></header><main>
{% with messages=get_flashed_messages() %}{% for m in messages %}<div class="flash">{{m}}</div>{% endfor %}{% endwith %}
<div class="cards"><div class="card"><span class="muted">Starting paper bankroll</span><strong>$100.00</strong></div><div class="card"><span class="muted">Stake per pick</span><strong>$20.00</strong></div><div class="card"><span class="muted">Minimum edge</span><strong>3 percentage points</strong></div></div>
<div class="notice"><b>Paper-only.</b> This app does not connect to Robinhood, read live contract prices, or place orders. Enter the YES price shown in Robinhood and a probability estimate from your analysis. This version calculates edge; it does not independently predict winners. Fees are not included yet.</div>
<section><h2>Analyze a contract</h2><div class="panel"><form method="post" action="{{url_for('analyze')}}"><div class="grid">
<div class="field"><label>Sport</label><select name="sport"><option>NFL</option><option>MLB</option><option>NBA</option></select></div>
<div class="field"><label>Matchup / event</label><input name="event" placeholder="Team A vs Team B" required></div>
<div class="field"><label>Contract / selection</label><input name="selection" placeholder="Team A wins" required></div>
<div class="field"><label>Robinhood YES price (cents)</label><input name="price" type="number" min="1" max="99" placeholder="60" required></div>
<div class="field"><label>Your estimated probability (%)</label><input name="prob" type="number" min="1" max="99" step=".1" placeholder="65" required></div>
</div><button class="submit">Calculate edge</button></form>
{% if a %}<div class="result"><div>Market-implied probability: <b>{{"%.1f"|format(a.implied)}}%</b></div><div>Estimated probability: <b>{{"%.1f"|format(a.prob)}}%</b></div><div>Estimated edge: <b class="{{'good' if a.edge>=3 else 'bad'}}">{{"%+.2f"|format(a.edge)}} percentage points</b></div><div>Profit if correct on $20, before fees: <b>${{"%.2f"|format(a.profit)}}</b></div><div class="muted">Potential payout including stake: ${{"%.2f"|format(a.payout)}}. Assumes each winning share pays $1.</div>
{% if a.edge>=3 %}<form method="post" action="{{url_for('save')}}"><input type="hidden" name="sport" value="{{a.sport}}"><input type="hidden" name="event" value="{{a.event}}"><input type="hidden" name="selection" value="{{a.selection}}"><input type="hidden" name="price" value="{{a.price}}"><input type="hidden" name="prob" value="{{a.prob}}"><button class="submit">Add to paper tracker ($20)</button></form>{% else %}<p class="bad"><b>Below the 3-point minimum.</b></p>{% endif %}</div>{% endif %}</div></section>
<section><h2>Paper tracker</h2><div class="tablewrap"><table><thead><tr><th>Added</th><th>Sport / event</th><th>Selection</th><th>Price</th><th>Estimated probability</th><th>Edge</th><th>Stake</th><th>Result</th></tr></thead><tbody>
{% for p in picks %}<tr><td>{{p.created_at}}</td><td>{{p.sport}}<br>{{p.event}}</td><td>{{p.selection}}</td><td>{{p.price}}¢</td><td>{{"%.1f"|format(p.probability*100)}}%</td><td>{{"%+.2f"|format(p.edge)}} pp</td><td>${{"%.2f"|format(p.stake)}}</td><td>{% if p.status=="Pending" %}<form method="post" action="{{url_for('settle',pid=p.id)}}"><select name="result"><option>Win</option><option>Loss</option><option>Push</option></select><button class="secondary">Save</button></form>{% else %}<b>{{p.status}}</b><br>P/L ${{"%.2f"|format(p.pnl)}}</td>{% endif %}</tr>{% else %}<tr><td colspan="8">No paper picks saved yet.</td></tr>{% endfor %}
</tbody></table></div></section><p class="muted">A 3-point edge is only useful if your probability estimates are accurate. Test against settled outcomes before relying on it. Free hosting may not preserve SQLite data if the instance is replaced.</p></main></body></html>
"""

@app.get("/")
def index():
    with db() as c: picks=c.execute("SELECT * FROM picks ORDER BY id DESC LIMIT 100").fetchall()
    return render_template_string(PAGE,picks=picks,a=None)

@app.post("/analyze")
def analyze():
    try:
        sport=request.form["sport"]; event=request.form["event"].strip(); selection=request.form["selection"].strip()
        price=int(request.form["price"]); prob=float(request.form["prob"])
        if sport not in SPORTS or not event or not selection or not 1<=price<=99 or not 1<=prob<=99: raise ValueError()
        edge=prob-price; shares=20/(price/100)
        a=dict(sport=sport,event=event,selection=selection,price=price,prob=prob,implied=price,edge=edge,profit=round(shares*(1-price/100),2),payout=round(shares,2))
    except (ValueError,KeyError):
        flash("Enter a valid event, price from 1–99 cents, and probability from 1–99%."); return redirect(url_for("index"))
    with db() as c: picks=c.execute("SELECT * FROM picks ORDER BY id DESC LIMIT 100").fetchall()
    return render_template_string(PAGE,picks=picks,a=a)

@app.post("/paper/save")
def save():
    try:
        sport=request.form["sport"]; event=request.form["event"].strip(); selection=request.form["selection"].strip()
        price=int(request.form["price"]); prob=float(request.form["prob"]); edge=prob-price
        if sport not in SPORTS or not event or not selection or not 1<=price<=99 or not 1<=prob<=99 or edge<MIN_EDGE: raise ValueError()
        with db() as c: c.execute("INSERT INTO picks (created_at,sport,event,selection,price,probability,edge,stake) VALUES (?,?,?,?,?,?,?,?)",(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),sport,event,selection,price,prob/100,edge,STAKE))
        flash("Saved as a paper pick only. No Robinhood order was placed.")
    except (ValueError,KeyError): flash("Pick not saved; it must meet the 3-point edge minimum.")
    return redirect(url_for("index"))

@app.post("/paper/settle/<int:pid>")
def settle(pid):
    result=request.form.get("result")
    if result not in {"Win","Loss","Push"}: return redirect(url_for("index"))
    with db() as c:
        p=c.execute("SELECT * FROM picks WHERE id=?",(pid,)).fetchone()
        if p and p["status"]=="Pending":
            shares=p["stake"]/(p["price"]/100)
            pnl=round(shares*(1-p["price"]/100),2) if result=="Win" else (-p["stake"] if result=="Loss" else 0.0)
            c.execute("UPDATE picks SET status=?,pnl=? WHERE id=?",(result,pnl,pid))
            flash(f"Paper result saved: {result}; simulated P/L ${pnl:.2f}.")
    return redirect(url_for("index"))

@app.get("/health")
def health(): return {"status":"ok"}

if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT","10000")))

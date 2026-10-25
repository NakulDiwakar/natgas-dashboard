# Tests the storage bias on the past year or two of reports: did price move the way the bias said?
import json, math, os, time, urllib.parse, urllib.request
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
SERIES = "NW2_EPG0_SWO_R48_BCF"

def get(url):
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:
            last = e
            print("Retrying after error:", e)
            time.sleep(5 * (attempt + 1))
    raise last

def storage(key):
    params = [("api_key", key), ("frequency", "weekly"), ("data[0]", "value"), ("start", "2018-01-01"),
              ("sort[0][column]", "period"), ("sort[0][direction]", "asc"), ("offset", "0"), ("length", "5000")]
    j = get("https://api.eia.gov/v2/natural-gas/stor/wkly/data/?" + urllib.parse.urlencode(params))
    rows = j["response"]["data"]
    levels = {}
    for r in rows:
        if r.get("series") == SERIES and r.get("value") not in (None, ""):
            levels[date.fromisoformat(r["period"])] = float(r["value"])
    if not levels:
        print("No Lower 48 rows found. Series seen:", sorted({str(r.get("series")) for r in rows})[:10])
    return levels

def prices():
    end = int(time.time())
    start = end - 725 * 86400
    j = get("https://query1.finance.yahoo.com/v8/finance/chart/NG=F?interval=1h&period1=%d&period2=%d" % (start, end))
    res = j["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    bars = {}
    for i, ts in enumerate(res["timestamp"]):
        o, c = q["open"][i], q["close"][i]
        if o is not None and c is not None and o != 0:
            bars[ts] = (o, c)
    return bars

def pct(a, b):
    return round((b - a) / a * 100, 2)

def stat(rs):
    n = len(rs)
    if n == 0:
        return {"n": 0}
    sg = lambda r: 1 if r["bias"] == "Bullish" else -1
    def rate(h):
        p = h / n
        e = 1.96 * math.sqrt(p * (1 - p) / n)
        return {"p": round(p * 100), "lo": round(max(0, p - e) * 100), "hi": round(min(1, p + e) * 100)}
    return {"n": n,
            "h1": rate(sum(1 for r in rs if r["m1"] * sg(r) > 0)),
            "h2": rate(sum(1 for r in rs if r["m2"] * sg(r) > 0)),
            "avg": round(sum(r["m1"] * sg(r) for r in rs) / n, 2)}

def main():
    key = os.environ.get("EIA_API_KEY")
    if not key:
        print("EIA_API_KEY secret is missing, skipping.")
        return
    levels = storage(key)
    days = sorted(levels)
    net = {d: levels[d] - levels[p] for p, d in zip(days, days[1:]) if (d - p).days == 7}

    def normal(d):
        vals = []
        for k in range(1, 6):
            try:
                tgt = d.replace(year=d.year - k)
            except ValueError:
                tgt = d.replace(year=d.year - k, day=28)
            near = [x for x in net if abs((x - tgt).days) <= 3]
            if near:
                vals.append(net[min(near, key=lambda x: abs((x - tgt).days))])
        return sum(vals) / len(vals) if len(vals) >= 4 else None

    bars = prices()
    today = date.today()
    rows = []
    for d in sorted(net):
        rel = d + timedelta(days=6)
        if rel.weekday() != 3 or rel >= today or (today - rel).days > 720:
            continue
        nm = normal(d)
        if nm is None:
            continue
        t0 = int(datetime(rel.year, rel.month, rel.day, 10, 0, tzinfo=NY).timestamp())
        b0, b1 = bars.get(t0), bars.get(t0 + 3600)
        if not b0 or not b1:
            continue
        s = nm - net[d]
        bias = "Bullish" if s >= 3 else "Bearish" if s <= -3 else "Neutral"
        rows.append({"date": str(rel), "net": round(net[d]), "normal": round(nm), "surprise": round(s),
                     "bias": bias, "m1": pct(b0[0], b0[1]), "m2": pct(b0[0], b1[1])})

    if len(rows) < 20:
        print("Too few reports matched with prices:", len(rows))
        return
    scored = [r for r in rows if r["bias"] != "Neutral"]
    out = {
        "updated": datetime.now(timezone.utc).isoformat(), "reports": len(rows),
        "first": rows[0]["date"], "last": rows[-1]["date"],
        "up_rate": round(sum(1 for r in rows if r["m1"] > 0) / len(rows) * 100),
        "groups": [
            {"name": "All scored reports", **stat(scored)},
            {"name": "Bullish bias", **stat([r for r in scored if r["bias"] == "Bullish"])},
            {"name": "Bearish bias", **stat([r for r in scored if r["bias"] == "Bearish"])},
            {"name": "Large surprise (7+ Bcf)", **stat([r for r in scored if abs(r["surprise"]) >= 7])},
        ],
    }
    with open("backtest.json", "w") as f:
        json.dump(out, f)
    print("Saved test of", len(rows), "reports,", len(scored), "scored")

try:
    main()
except Exception as e:
    print("Backtest skipped:", e)

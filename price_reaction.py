# Records how natural gas futures price moved right after each storage report
import json, os, urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
URL = "https://query1.finance.yahoo.com/v8/finance/chart/NG=F?interval=5m&range=30d"

def get_bars():
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        res = json.load(r)["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    bars = {}
    for i, ts in enumerate(res["timestamp"]):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None not in (o, h, l, c):
            bars[ts] = (o, h, l, c)
    return bars

def pct(a, b):
    return round((b - a) / a * 100, 2)

def main():
    data = json.load(open("data.json"))
    L = data.get("latest")
    if not L:
        print("No storage report saved yet.")
        return
    rx = json.load(open("reactions.json")) if os.path.exists("reactions.json") else {"rows": []}
    if any(r["week"] == L["week"] for r in rx["rows"]):
        print("Price reaction already saved for", L["week"])
        return

    t0dt = datetime.strptime(L["released"], "%Y-%m-%d").replace(hour=10, minute=30, tzinfo=NY)
    if datetime.now(timezone.utc) < t0dt + timedelta(minutes=70):
        print("Too early, waiting for an hour of price data after the report.")
        return
    t0 = int(t0dt.timestamp())

    bars = get_bars()
    if t0 not in bars:
        print("No price bar found at release time. Skipping.")
        return
    base = bars[t0][0]

    def after(mins):
        b = bars.get(t0 + (mins - 5) * 60)
        return pct(base, b[3]) if b else None

    window = [bars[t0 + i * 300] for i in range(6) if (t0 + i * 300) in bars]
    swing = round((max(b[1] for b in window) - min(b[2] for b in window)) / base * 100, 2)
    m5, m15, m60 = after(5), after(15), after(60)

    match = None
    if m15 is not None:
        if L["bias"] == "Bullish":
            match = m15 > 0
        elif L["bias"] == "Bearish":
            match = m15 < 0

    rx["rows"] = (rx["rows"] + [{
        "week": L["week"], "released": L["released"], "bias": L["bias"],
        "basis": L["basis"], "m5": m5, "m15": m15, "m60": m60,
        "swing": swing, "match": match,
    }])[-100:]
    with open("reactions.json", "w") as f:
        json.dump(rx, f, indent=1)
    print("Saved price reaction for", L["week"], "15 min move", m15)

try:
    main()
except Exception as e:
    print("Price check skipped:", e)

# Builds a table of how much natural gas futures usually move in each hour (India time)
import json, os, urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
URL = "https://query1.finance.yahoo.com/v8/finance/chart/NG=F?interval=1h&range=1y"
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]

def main():
    # Rebuild once a week, or right away when the US clock change moves India times
    offset_min = int((timedelta(hours=5, minutes=30) - datetime.now(NY).utcoffset()).total_seconds() // 60)
    if os.path.exists("heatmap.json"):
        old = json.load(open("heatmap.json"))
        if old.get("updated") and old.get("offset_min") == offset_min:
            age = datetime.now(timezone.utc) - datetime.fromisoformat(old["updated"])
            if age < timedelta(days=6):
                print("Heatmap is fresh, skipping.")
                return

    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        res = json.load(r)["chart"]["result"][0]
    q = res["indicators"]["quote"][0]

    # Line up winter and summer on the US exchange clock, then show in today's India time
    delta = timedelta(hours=5, minutes=30) - datetime.now(NY).utcoffset()

    cells = {}
    for i, ts in enumerate(res["timestamp"]):
        o, h, l = q["open"][i], q["high"][i], q["low"][i]
        if None in (o, h, l) or o == 0:
            continue
        t = datetime.fromtimestamp(ts, NY).replace(tzinfo=None) + delta
        if t.weekday() > 4 or t.hour < 9:
            continue
        key = (f"{t.hour:02d}:{t.minute:02d}", t.weekday())
        cells.setdefault(key, []).append((h - l) / o * 100)

    times = sorted({k[0] for k in cells})
    rows = []
    for tm in times:
        vals = []
        for d in range(5):
            v = cells.get((tm, d), [])
            vals.append(round(sum(v) / len(v), 2) if len(v) >= 5 else None)
        if any(v is not None for v in vals):
            rows.append({"time": tm, "vals": vals})

    out = {"updated": datetime.now(timezone.utc).isoformat(), "offset_min": offset_min, "days": DAYS, "rows": rows}
    with open("heatmap.json", "w") as f:
        json.dump(out, f)
    print("Saved heatmap with", len(rows), "time slots")

try:
    main()
except Exception as e:
    print("Heatmap skipped:", e)

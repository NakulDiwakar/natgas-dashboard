# Reads EIA's free weekly gas storage report and saves a simple bias to data.json
import json, os, urllib.request
from datetime import datetime

URL = "https://ir.eia.gov/ngs/wngsr.json"
FILE = "data.json"

def load():
    if os.path.exists(FILE):
        with open(FILE) as f:
            return json.load(f)
    return {"latest": None, "history": []}

def day(text):
    return datetime.strptime(text, "%Y-%m-%d").date()

def main():
    req = urllib.request.Request(URL, headers={"User-Agent": "natgas-dashboard"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = json.load(r)

    total = next(s for s in raw["series"] if s["name"] == "total lower 48 states")
    calc = total["calculated"]
    week = raw["current_week"]
    avg5 = calc["5yr-avg"]
    net = calc["net_change"]
    dev = calc["pct-chg_5yr-avg"]
    released = datetime.strptime(raw["release_date"], "%Y-%b-%d %H:%M:%S").strftime("%Y-%m-%d")

    data = load()
    if any(h["week"] == week for h in data["history"]):
        print("No new report yet. Latest saved week:", week)
        return

    prev = data["history"][-1] if data["history"] else None
    normal = surprise = None
    if prev and (day(week) - day(prev["week"])).days == 7:
        normal = avg5 - prev["avg5"]      # normal change for this week
        surprise = normal - net           # positive = less gas added than normal = bullish
        basis = "weekly"
        bias = "Bullish" if surprise >= 3 else "Bearish" if surprise <= -3 else "Neutral"
    else:
        basis = "level"                   # first report: only compare stock level with normal
        bias = "Bullish" if dev <= -2 else "Bearish" if dev >= 2 else "Neutral"

    entry = {"week": week, "avg5": avg5, "net_change": net}
    data["history"] = (data["history"] + [entry])[-60:]
    data["latest"] = {
        "week": week, "released": released, "net_change": net,
        "normal_change": normal, "surprise": surprise, "level_vs_normal_pct": dev,
        "basis": basis, "bias": bias,
        "updated_utc": datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
    }
    with open(FILE, "w") as f:
        json.dump(data, f, indent=1)
    print("Saved report for week", week, "bias", bias)

main()

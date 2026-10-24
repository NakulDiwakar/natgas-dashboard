# Compares the next 7 days of weather in big US gas-heating cities with the last 5 years
import json, os, urllib.request
from datetime import date, datetime, timedelta, timezone

CITIES = [("New York", 40.71, -74.01), ("Chicago", 41.88, -87.63), ("Boston", 42.36, -71.06),
          ("Philadelphia", 39.95, -75.17), ("Detroit", 42.33, -83.05)]
DAYS = 7

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "natgas-dashboard"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs)

def main():
    if os.path.exists("weather.json"):
        old = json.load(open("weather.json"))
        if old.get("updated"):
            age = datetime.now(timezone.utc) - datetime.fromisoformat(old["updated"])
            if age < timedelta(hours=20):
                print("Weather is fresh, skipping.")
                return

    today = date.today()
    rows = []
    for name, lat, lon in CITIES:
        f = get("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
                "&daily=temperature_2m_mean&forecast_days=%d&timezone=auto" % (lat, lon, DAYS))
        forecast = mean(f["daily"]["temperature_2m_mean"])
        past = []
        for k in range(1, 6):
            try:
                start = today.replace(year=today.year - k)
            except ValueError:
                start = today.replace(year=today.year - k, day=28)
            end = start + timedelta(days=DAYS - 1)
            a = get("https://archive-api.open-meteo.com/v1/archive?latitude=%s&longitude=%s"
                    "&start_date=%s&end_date=%s&daily=temperature_2m_mean&timezone=auto" % (lat, lon, start, end))
            past.append(mean(a["daily"]["temperature_2m_mean"]))
        normal = mean(past)
        rows.append({"name": name, "forecast": round(forecast, 1), "normal": round(normal, 1),
                     "diff": round(forecast - normal, 1)})

    diff = round(mean([r["diff"] for r in rows]), 1)
    m = today.month
    if m in (11, 12, 1, 2, 3):
        season = "heating"
        lean = "Bullish" if diff <= -1.5 else "Bearish" if diff >= 1.5 else "Neutral"
    elif m in (6, 7, 8):
        season = "cooling"
        lean = "Bullish" if diff >= 1.5 else "Bearish" if diff <= -1.5 else "Neutral"
    else:
        season = "mild"
        lean = "Neutral"

    out = {"updated": datetime.now(timezone.utc).isoformat(), "season": season,
           "diff": diff, "lean": lean, "rows": rows}
    with open("weather.json", "w") as f:
        json.dump(out, f)
    print("Saved weather: diff", diff, "lean", lean)

try:
    main()
except Exception as e:
    print("Weather skipped:", e)

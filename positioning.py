# Reads the free weekly CFTC report on how big funds are positioned in US natural gas futures
import json, os, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

BASE = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json"

def main():
    if os.path.exists("positioning.json"):
        old = json.load(open("positioning.json"))
        if old.get("updated"):
            age = datetime.now(timezone.utc) - datetime.fromisoformat(old["updated"])
            if age < timedelta(hours=20):
                print("Positioning is fresh, skipping.")
                return

    params = {
        "cftc_contract_market_code": "023651",
        "$select": "report_date_as_yyyy_mm_dd,open_interest_all,m_money_positions_long_all,m_money_positions_short_all",
        "$order": "report_date_as_yyyy_mm_dd DESC",
        "$limit": "160",
    }
    req = urllib.request.Request(BASE + "?" + urllib.parse.urlencode(params),
                                 headers={"User-Agent": "natgas-dashboard"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = json.load(r)

    rows = []
    for x in raw:
        oi = float(x["open_interest_all"])
        net = int(float(x["m_money_positions_long_all"])) - int(float(x["m_money_positions_short_all"]))
        rows.append({"d": x["report_date_as_yyyy_mm_dd"][:10], "net": net, "pct": net / oi * 100})
    if len(rows) < 52:
        print("Not enough weeks of data:", len(rows))
        return

    cur, prev = rows[0], rows[1]
    rank = round(sum(1 for r in rows if r["pct"] <= cur["pct"]) / len(rows) * 100)
    if rank >= 90:
        state, lean = "Crowded long: pullback risk", "Bearish"
    elif rank <= 10:
        state, lean = "Crowded short: squeeze risk", "Bullish"
    else:
        state, lean = "Not crowded", "Neutral"

    out = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "report_date": cur["d"], "net": cur["net"], "net_pct": round(cur["pct"], 1),
        "percentile": rank, "weeks": len(rows), "change": cur["net"] - prev["net"],
        "state": state, "lean": lean,
    }
    with open("positioning.json", "w") as f:
        json.dump(out, f)
    print("Saved positioning for", cur["d"], "percentile", rank)

try:
    main()
except Exception as e:
    print("Positioning skipped:", e)

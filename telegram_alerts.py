# Sends two Telegram messages: a heads-up before the storage report, and the bias once it is out
import json, os, urllib.parse, urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
IST = ZoneInfo("Asia/Kolkata")
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT = os.environ.get("TELEGRAM_CHAT_ID")

def send(text):
    url = "https://api.telegram.org/bot" + TOKEN + "/sendMessage"
    body = urllib.parse.urlencode({"chat_id": CHAT, "text": text}).encode()
    urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=30).read()

def load(name, default):
    if os.path.exists(name):
        with open(name) as f:
            return json.load(f)
    return default

def main():
    if not TOKEN or not CHAT:
        print("Telegram secrets are missing, skipping.")
        return
    state = load("alerts.json", {"sent": []})
    sent = state["sent"]
    changed = False
    now = datetime.now(timezone.utc)
    et = now.astimezone(NY)

    # One-time test message when you press Run workflow by hand
    if os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and "test" not in sent:
        send("Test message: your natural gas alerts are connected.")
        sent.append("test")
        changed = True

    # 1. Heads-up about 15 to 45 minutes before the Thursday report
    release = et.replace(hour=10, minute=30, second=0, microsecond=0)
    mins = (release - et).total_seconds() / 60
    key = str(et.date()) + "-pre"
    if et.weekday() == 3 and 15 <= mins <= 45 and key not in sent:
        when = release.astimezone(IST).strftime("%I:%M %p").lstrip("0")
        send("Gas storage report in about " + str(int(mins)) + " minutes (" + when +
             " India time). Price can swing both ways, so be careful with new zone trades.")
        sent.append(key)
        changed = True

    # 2. Bias message after the report is saved
    L = load("data.json", {"latest": None}).get("latest")
    if L and (L["week"] + "-bias") not in sent:
        updated = datetime.strptime(L["updated_utc"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        if (now - updated).total_seconds() < 3 * 3600:
            lean = {"Bullish": "leaning up", "Bearish": "leaning down"}.get(L["bias"], "no clear lean")
            lines = ["US gas stock report is out. Overall: " + lean + "."]
            if L["basis"] == "weekly":
                def chg(v):
                    return ("rose by " if v >= 0 else "fell by ") + str(abs(round(v))) + " billion cubic feet"
                lines.append("Gas in storage " + chg(L["net_change"]) + ". A normal week at this time of year: " + chg(L["normal_change"]) + ".")
            else:
                d = L["level_vs_normal_pct"]
                lines.append("US gas storage is " + str(abs(d)) + "% " + ("below" if d < 0 else "above") + " the five-year average.")
            lines.append("Expect wild swings for about 2 hours.")
            send("\n".join(lines))
        sent.append(L["week"] + "-bias")
        changed = True

    if changed:
        state["sent"] = sent[-40:]
        with open("alerts.json", "w") as f:
            json.dump(state, f)

try:
    main()
except Exception as e:
    print("Alerts skipped:", e)

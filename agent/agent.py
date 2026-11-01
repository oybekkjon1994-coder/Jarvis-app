"""Jarvis 24/7 agent — GitHub Actions'da bepul ishlaydi.
Vazifalar: (1) dollar kursi kuzatuvi, (2) OLX'da yangi buyurtma e'lonlarini qidirish.
Xabarlar Telegram'ga keladi. Holat state.json'da saqlanadi.
"""
import json, os, sys, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state.json")
CFG = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
UA = {"User-Agent": "Mozilla/5.0 (JarvisAgent)"}


def get_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def notify(text):
    print("NOTIFY:", text)
    if not (TOKEN and CHAT):
        return
    data = urllib.parse.urlencode({"chat_id": CHAT, "text": text, "disable_web_page_preview": "true"}).encode()
    urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data=data), timeout=30)


def load_state():
    try:
        return json.load(open(STATE, encoding="utf-8"))
    except Exception:
        return {"usd": None, "seen": []}


def check_usd(st):
    rate = None
    for fn in (lambda: float(get_json("https://cbu.uz/oz/arkhiv-kursov-valyut/json/USD/")[0]["Rate"]),
               lambda: float(get_json("https://open.er-api.com/v6/latest/USD")["rates"]["UZS"])):
        try:
            rate = fn(); break
        except Exception as e:
            print("USD xato:", e)
    if rate is None:
        return
    old = st.get("usd")
    thr = CFG.get("usd_change_percent", 0.5)
    if old and abs(rate - old) / old * 100 >= thr:
        notify(f"💵 Dollar kursi o'zgardi: {old:,.2f} → {rate:,.2f} so'm")
    st["usd"] = rate


def check_olx(st):
    seen = set(st.get("seen", []))
    first_run = not seen
    for q in CFG.get("olx_queries", []):
        try:
            url = "https://www.olx.uz/api/v1/offers/?" + urllib.parse.urlencode({"query": q, "limit": 40, "sort_by": "created_at:desc"})
            offers = get_json(url).get("data", [])
        except Exception as e:
            print("OLX xato:", q, e); continue
        for o in offers:
            oid = str(o.get("id"))
            if oid in seen:
                continue
            seen.add(oid)
            if not first_run:
                notify(f"🔎 Yangi e'lon ({q}):\n{o.get('title')}\n{o.get('url')}")
    st["seen"] = list(seen)[-500:]


if __name__ == "__main__":
    st = load_state()
    check_usd(st)
    check_olx(st)
    json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

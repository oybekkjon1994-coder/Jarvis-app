"""Jarvis 24/7 agent — GitHub Actions'da bepul ishlaydi.
Vazifalar: (1) dollar kursi, (2) OLX'da yangi buyurtma e'lonlari, (3) Telegram ochiq kanallarida kalit so'zlar.
Xabarlar Telegram'ga keladi. Holat state.json'da, panel uchun natija feed.json'da saqlanadi.
"""
import html, json, os, re, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state.json")
FEED = os.path.join(HERE, "feed.json")
CFG = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
UA = {"User-Agent": "Mozilla/5.0 (JarvisAgent)"}
TZ = timezone(timedelta(hours=5))
NOW = datetime.now(TZ)
FEED_MAX = 60

errors = []


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def get_json(url):
    return json.loads(fetch(url))


def notify(text):
    print("NOTIFY:", text)
    if not (TOKEN and CHAT):
        return
    data = urllib.parse.urlencode({"chat_id": CHAT, "text": text, "disable_web_page_preview": "true"}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data=data), timeout=30)
    except Exception as e:
        errors.append(f"telegram: {e}")


def load_json(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def add_feed(feed, item):
    item["at"] = NOW.strftime("%Y-%m-%d %H:%M")
    feed["items"].insert(0, item)
    del feed["items"][FEED_MAX:]


def check_usd(st, feed):
    rate = None
    for fn in (lambda: float(get_json("https://cbu.uz/oz/arkhiv-kursov-valyut/json/USD/")[0]["Rate"]),
               lambda: float(get_json("https://open.er-api.com/v6/latest/USD")["rates"]["UZS"])):
        try:
            rate = fn(); break
        except Exception as e:
            print("USD xato:", e)
    if rate is None:
        errors.append("usd: manbalar javob bermadi")
        return
    old = st.get("usd")
    thr = CFG.get("usd_change_percent", 0.5)
    if old and abs(rate - old) / old * 100 >= thr:
        notify(f"💵 Dollar kursi o'zgardi: {old:,.2f} → {rate:,.2f} so'm")
        feed["usd_changed"] = NOW.strftime("%Y-%m-%d %H:%M")
    st["usd"] = rate
    feed["usd"] = round(rate, 2)


def olx_price(o):
    for p in o.get("params", []):
        if p.get("key") == "price" and isinstance(p.get("value"), dict):
            return p["value"].get("label") or ""
    return ""


def olx_ok(o):
    """Ish e'lonlari, eski (yangilab turilgan) va keraksiz so'zli e'lonlarni o'tkazib yuboradi."""
    if (o.get("category") or {}).get("type") in CFG.get("olx_exclude_types", ["job"]):
        return False
    title = (o.get("title") or "").lower()
    if any(w.lower() in title for w in CFG.get("olx_exclude_words", [])):
        return False
    try:
        created = datetime.fromisoformat(o.get("created_time"))
        if NOW - created > timedelta(days=CFG.get("olx_max_age_days", 7)):
            return False
    except Exception:
        pass
    return True


def check_olx(st, feed):
    seen = set(st.get("seen", []))
    done = set(st.get("queries_done", []))
    for q in CFG.get("olx_queries", []):
        silent = q not in done  # yangi so'z birinchi marta: xabar yubormaymiz, faqat panelga yozamiz
        try:
            url = "https://www.olx.uz/api/v1/offers/?" + urllib.parse.urlencode({"query": q, "limit": 40, "sort_by": "created_at:desc"})
            offers = get_json(url).get("data", [])
        except Exception as e:
            errors.append(f"olx '{q}': {e}")
            continue
        for o in offers:
            oid = str(o.get("id"))
            if oid in seen:
                continue
            seen.add(oid)
            if not olx_ok(o):
                continue
            city = ((o.get("location") or {}).get("city") or {}).get("name", "")
            price = olx_price(o)
            add_feed(feed, {"src": "olx", "q": q, "title": o.get("title"), "url": o.get("url"), "price": price, "city": city})
            if not silent:
                notify(f"🔎 OLX ({q}):\n{o.get('title')}\n{price} {city}".rstrip() + f"\n{o.get('url')}")
        done.add(q)
    st["seen"] = list(seen)[-1500:]
    st["queries_done"] = sorted(done)


def tg_messages(channel):
    page = fetch(f"https://t.me/s/{channel}")
    out = []
    for chunk in page.split('data-post="')[1:]:
        m = re.match(r"([\w]+)/(\d+)", chunk)
        t = re.search(r'tgme_widget_message_text[^>]*>(.*?)</div>', chunk, re.S)
        if not (m and t):
            continue
        text = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<br\s*/?>", "\n", t.group(1))))
        out.append((int(m.group(2)), re.sub(r"[ \t]+", " ", text).strip()))
    return out


def check_channels(st, feed):
    kws = [k.lower() for k in CFG.get("telegram_keywords", [])]
    last = st.setdefault("tg_last", {})
    for ch in CFG.get("telegram_channels", []):
        ch = ch.lstrip("@")
        try:
            msgs = tg_messages(ch)
        except Exception as e:
            errors.append(f"kanal @{ch}: {e}")
            continue
        silent = ch not in last
        prev = last.get(ch, 0)
        for mid, text in msgs:
            if mid <= prev or not any(k in text.lower() for k in kws):
                continue
            url = f"https://t.me/{ch}/{mid}"
            add_feed(feed, {"src": "tg", "q": "@" + ch, "title": text[:140], "url": url, "price": "", "city": ""})
            if not silent:
                notify(f"📢 @{ch}:\n{text[:400]}\n{url}")
        if msgs:
            last[ch] = max(prev, max(m[0] for m in msgs))


if __name__ == "__main__":
    st = load_json(STATE, {})
    feed = load_json(FEED, {})
    feed.setdefault("items", [])
    check_usd(st, feed)
    check_olx(st, feed)
    check_channels(st, feed)
    feed["updated"] = NOW.strftime("%Y-%m-%d %H:%M")
    feed["errors"] = errors[:10]
    feed["watching"] = {"olx": CFG.get("olx_queries", []), "channels": CFG.get("telegram_channels", [])}
    json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(feed, open(FEED, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for e in errors:
        print("XATO:", e)

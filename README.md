# Jarvis agent (24/7, bepul)

GitHub Actions har 30 daqiqada ishlaydi: dollar kursi o'zgarsa va OLX'da yangi buyurtma e'loni chiqsa, Telegram'ga xabar yuboradi.

## Sozlash
Repo → Settings → Secrets and variables → Actions:
- `TELEGRAM_BOT_TOKEN` — @BotFather'dan olingan token
- `TELEGRAM_CHAT_ID` — sizning chat ID (@userinfobot orqali)

So'ng Actions → "Jarvis agent" → Run workflow. Qidiruv so'zlari: `agent/config.json`.

## Kuzatuvchilar
- **OLX**: `olx_queries` bo'yicha yangi e'lonlar. Ish e'lonlari (`olx_exclude_types`), `olx_max_age_days` dan eski va `olx_exclude_words` so'zli e'lonlar o'tkazib yuboriladi. Yangi qo'shilgan so'z birinchi marta xabar yubormaydi, faqat panelga yoziladi.
- **Telegram kanallar**: `telegram_channels` ga ochiq kanal nomini yozing (masalan `"kanal_nomi"`), `telegram_keywords` dan biri uchragan postlar yuboriladi. Kanal ochiq bo'lishi kerak (t.me/s/…).
- **Panel**: natija `agent/feed.json` ga yoziladi; metartshop `boshqaruv.html` shuni ko'rsatadi.

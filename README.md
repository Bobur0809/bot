# Yuvvosh Mushukcha boti — GitHub Actions'da 24/7

Bot GitHub serverida ishlaydi: ~5 soat 45 daqiqa ishlab, keyingisini o'zi
ishga tushiradi. Token, flag va maxfiy so'z kodda emas — GitHub Secrets'da.

## Lokal ishga tushirish
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export BOT_TOKEN="..." FLAG="..." SECRET_WORDS="soz1,soz2"
python bot.py config.json
```

## Media
`media/1.mp4` … `7.mp4` — noto'g'ri javoblar (navbat bilan), `help.mp4` — /help,
`flag.mp4` — to'g'ri javob. Fayl topilmasa faqat matn yuboriladi.

## To'xtatish
GitHub → Actions → "Telegram bot" → "…" → **Disable workflow**,
so'ng ishlab turgan run'ni **Cancel** qiling.

## Flag tekshiruvchi bot (`checker.py`)
O'quvchi flagni yuboradi → "✅ To'g'ri" / "❌ Noto'g'ri". To'g'ri topshirilsa,
`ADMIN_CHAT_ID` ga xabar boradi (kim, qachon). `/stat` — yechganlar ro'yxati (faqat admin).
GitHub Secrets: `CHECKER_TOKEN`, `ADMIN_CHAT_ID` (flag `FLAG` dan olinadi).
Admin avval tekshiruvchi botga `/start` bosgan bo'lishi kerak.

"""Flag tekshiruvchi bot (aiogram 3).

Ishga tushirish:
    export CHECKER_TOKEN=123456:ABC...   # tekshiruvchi botning tokeni
    export FLAG='CTF{...}'               # to'g'ri flag (bir nechta bo'lsa: FLAGS='a|b')
    export ADMIN_CHAT_ID=123456789       # yechganlar haqida xabar shu odamga boradi
    export RUN_SECONDS=20700             # ixtiyoriy: shuncha soniyadan keyin o'zi to'xtaydi
    python checker.py
"""

import asyncio
import html
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

try:
    from zoneinfo import ZoneInfo

    TZ = ZoneInfo("Asia/Tashkent")
except Exception:  # tz bazasi bo'lmasa
    TZ = timezone(timedelta(hours=5))

TEXTS = {
    "start": (
        "🚩 <b>Flag tekshiruvchi</b>\n\n"
        "Topgan flagingizni shu yerga yuboring.\n"
        "Format: <code>CTF{...}</code>"
    ),
    "correct": "✅ <b>To'g'ri!</b> Tabriklayman, {name}! Natijangiz qayd etildi 🏆",
    "again": "✅ To'g'ri, lekin siz bu flagni allaqachon topshirgansiz 😉",
    "wrong": "❌ Noto'g'ri flag. Yana urinib ko'ring!",
}


def clean(text: str) -> str:
    return text.strip().strip("`").strip()


def who(m: Message) -> str:
    u = m.from_user
    name = html.escape(u.full_name or "?")
    username = f" (@{html.escape(u.username)})" if u.username else ""
    return f"{name}{username}, ID: <code>{u.id}</code>"


def build(flags: set[str], admin_id: int | None) -> Dispatcher:
    solved: dict[int, datetime] = {}  # user_id -> vaqt (shu ishga tushirish davomida)
    names: dict[int, str] = {}
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def start(m: Message) -> None:
        await m.answer(TEXTS["start"])

    @dp.message(Command("stat"))
    async def stat(m: Message) -> None:
        if admin_id is None or m.from_user.id != admin_id:
            await m.answer(TEXTS["wrong"])
            return
        if not solved:
            await m.answer("Hozircha hech kim yechmadi (bot oxirgi ishga tushgandan beri).")
            return
        lines = [
            f"{i}. {names[uid]} — {t:%d.%m %H:%M:%S}"
            for i, (uid, t) in enumerate(sorted(solved.items(), key=lambda x: x[1]), 1)
        ]
        await m.answer("🏆 Yechganlar (bot oxirgi ishga tushgandan beri):\n\n" + "\n".join(lines))

    @dp.message(F.text)
    async def check(m: Message) -> None:
        if clean(m.text) not in flags:
            await m.answer(TEXTS["wrong"])
            return
        uid = m.from_user.id
        if uid in solved:
            await m.answer(TEXTS["again"])
            return
        now = datetime.now(TZ)
        solved[uid] = now
        names[uid] = who(m)
        logging.info("solved user_id=%s", uid)
        await m.answer(TEXTS["correct"].format(name=html.escape(m.from_user.first_name or "")))
        if admin_id is not None:
            try:
                await m.bot.send_message(
                    admin_id,
                    f"🏆 <b>Flag topshirildi!</b>\n👤 {names[uid]}\n🕐 {now:%d.%m.%Y %H:%M:%S}",
                )
            except Exception as e:  # admin botga /start bosmagan bo'lsa ham o'quvchiga ta'sir qilmasin
                logging.warning("adminga xabar yuborilmadi: %s", type(e).__name__)

    @dp.message()
    async def other(m: Message) -> None:
        await m.answer(TEXTS["wrong"])

    return dp


async def main() -> None:
    token = os.environ.get("CHECKER_TOKEN")
    if not token:
        sys.exit("CHECKER_TOKEN o'rnatilmagan")
    raw = os.environ.get("FLAGS") or os.environ.get("FLAG") or ""
    flags = {f.strip() for f in raw.split("|") if f.strip()}
    if not flags:
        sys.exit("FLAG (yoki FLAGS) o'rnatilmagan")
    admin = os.environ.get("ADMIN_CHAT_ID", "").strip()
    admin_id = int(admin) if admin.lstrip("-").isdigit() else None
    logging.basicConfig(level=logging.INFO)
    if admin_id is None:
        logging.warning("ADMIN_CHAT_ID yo'q: yechganlar haqida xabar yuborilmaydi")

    dp = build(flags, admin_id)
    bot = Bot(token, default=DefaultBotProperties(parse_mode="HTML"))

    run_seconds = int(os.environ.get("RUN_SECONDS", "0"))
    if run_seconds > 0:
        async def stop_later() -> None:
            await asyncio.sleep(run_seconds)
            logging.info("RUN_SECONDS tugadi, bot to'xtayapti")
            await dp.stop_polling()

        asyncio.create_task(stop_later())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

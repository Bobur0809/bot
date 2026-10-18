"""Flag tekshiruvchi bot (aiogram 3): dinamik ball, First Blood va reyting.

Ishga tushirish:
    export CHECKER_TOKEN=123456:ABC...   # tekshiruvchi botning tokeni
    export FLAG='CTF{...}'               # to'g'ri flag (bir nechta bo'lsa: FLAGS='a|b')
    export ADMIN_CHAT_ID=123456789       # yechganlar haqida xabar va reyting saqlanadigan joy
    export ANNOUNCE_CHAT_ID=-100123...   # ixtiyoriy: First Blood e'loni shu kanal/guruhga
    export RUN_SECONDS=20700             # ixtiyoriy: shuncha soniyadan keyin o'zi to'xtaydi
    python checker.py

Reyting bot qayta ishga tushganda yo'qolmasligi uchun admin bilan shaxsiy chatdagi
pin qilingan xabarda saqlanadi (o'sha xabarni o'chirmang va unpin qilmang).
"""

import asyncio
import html
import json
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

# Dinamik ball: 1-o'rin MAX_POINTS, har keyingi o'rin STEP kam, lekin MIN_POINTS dan kam emas
MAX_POINTS = int(os.environ.get("MAX_POINTS", "500"))
STEP = int(os.environ.get("POINTS_STEP", "50"))
MIN_POINTS = int(os.environ.get("MIN_POINTS", "100"))

STATE_MARK = "📊 REYTING MA'LUMOTLARI (o'chirmang, unpin qilmang)"

TEXTS = {
    "start": (
        "🚩 <b>Flag tekshiruvchi</b>\n\n"
        "Topgan flagingizni shu yerga yuboring.\n"
        "Format: <code>CTF{...}</code>\n\n"
        "🏆 Reyting: /reyting"
    ),
    "first_blood": (
        "🩸 <b>FIRST BLOOD!</b> 🩸\n\n"
        "Tabriklayman, {name}! Siz birinchi bo'lib yechdingiz!\n"
        "🏅 1-o'rin · <b>{points} ball</b>\n\n🏆 /reyting"
    ),
    "correct": (
        "✅ <b>To'g'ri!</b> Tabriklayman, {name}!\n"
        "🏅 {place}-o'rin · <b>{points} ball</b>\n\n🏆 /reyting"
    ),
    "again": "✅ To'g'ri, lekin siz allaqachon topshirgansiz: {place}-o'rin, {points} ball 😉",
    "wrong": "❌ Noto'g'ri flag. Yana urinib ko'ring!",
    "empty": "🏆 Reyting hozircha bo'sh. Birinchi bo'lib yech va 🩸 First Blood ol!",
}


def points_for(place: int) -> int:
    return max(MIN_POINTS, MAX_POINTS - STEP * (place - 1))


def clean(text: str) -> str:
    return text.strip().strip("`").strip()


def leaderboard(solves: list[dict], admin: bool = False) -> str:
    if not solves:
        return TEXTS["empty"]
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = ["🏆 <b>Reyting</b>\n"]
    for i, s in enumerate(solves, 1):
        name = html.escape(s["name"])
        user = f" (@{html.escape(s['user'])})" if s.get("user") else ""
        blood = " 🩸" if i == 1 else ""
        t = datetime.fromisoformat(s["t"]).astimezone(TZ)
        extra = f" · ID <code>{s['id']}</code>" if admin else ""
        lines.append(
            f"{medals.get(i, f'{i}.')} {name}{user}{blood} — <b>{s['p']}</b> ball · {t:%d.%m %H:%M}{extra}"
        )
    return "\n".join(lines)


class Store:
    """Reytingni admin chatidagi pin qilingan xabarda saqlaydi."""

    def __init__(self, bot: Bot, admin_id: int | None):
        self.bot, self.admin_id = bot, admin_id
        self.solves: list[dict] = []
        self.msg_id: int | None = None

    async def load(self) -> None:
        if self.admin_id is None:
            return
        try:
            chat = await self.bot.get_chat(self.admin_id)
            pinned = chat.pinned_message
            if pinned and pinned.text and pinned.text.startswith(STATE_MARK):
                self.solves = json.loads(pinned.text[len(STATE_MARK):].strip())["solves"]
                self.msg_id = pinned.message_id
                logging.info("reyting yuklandi: %d ta yechim", len(self.solves))
        except Exception as e:
            logging.warning("reyting yuklanmadi: %s", type(e).__name__)

    async def save(self) -> None:
        if self.admin_id is None:
            return
        text = STATE_MARK + "\n" + json.dumps({"solves": self.solves}, ensure_ascii=False, separators=(",", ":"))
        try:
            if self.msg_id is not None:
                await self.bot.edit_message_text(text, chat_id=self.admin_id, message_id=self.msg_id, parse_mode=None)
                return
        except Exception as e:
            logging.warning("reyting xabari tahrirlanmadi, yangisi yuboriladi: %s", type(e).__name__)
        try:
            m = await self.bot.send_message(self.admin_id, text, parse_mode=None, disable_notification=True)
            await self.bot.pin_chat_message(self.admin_id, m.message_id, disable_notification=True)
            self.msg_id = m.message_id
        except Exception as e:
            logging.warning("reyting saqlanmadi: %s", type(e).__name__)


def build(flags: set[str], admin_id: int | None, announce_id: int | None, store: Store) -> Dispatcher:
    lock = asyncio.Lock()
    dp = Dispatcher()

    def find(uid: int) -> int | None:
        for i, s in enumerate(store.solves, 1):
            if s["id"] == uid:
                return i
        return None

    @dp.message(CommandStart())
    async def start(m: Message) -> None:
        await m.answer(TEXTS["start"])

    @dp.message(Command("reyting", "reyt", "scoreboard", "top"))
    async def rating(m: Message) -> None:
        await m.answer(leaderboard(store.solves))

    @dp.message(Command("stat"))
    async def stat(m: Message) -> None:
        if admin_id is None or m.from_user.id != admin_id:
            await m.answer(TEXTS["wrong"])
            return
        await m.answer(leaderboard(store.solves, admin=True))

    @dp.message(F.text)
    async def check(m: Message) -> None:
        if clean(m.text) not in flags:
            await m.answer(TEXTS["wrong"])
            return
        u = m.from_user
        name = html.escape(u.first_name or "")
        async with lock:
            place = find(u.id)
            if place is not None:
                await m.answer(TEXTS["again"].format(place=place, points=store.solves[place - 1]["p"]))
                return
            place = len(store.solves) + 1
            pts = points_for(place)
            now = datetime.now(TZ)
            store.solves.append(
                {"id": u.id, "name": u.full_name or "?", "user": u.username or "", "t": now.isoformat(), "p": pts}
            )
            await store.save()
        logging.info("solved user_id=%s place=%s", u.id, place)

        if place == 1:
            await m.answer(TEXTS["first_blood"].format(name=name, points=pts))
        else:
            await m.answer(TEXTS["correct"].format(name=name, place=place, points=pts))

        who = html.escape(u.full_name or "?") + (f" (@{html.escape(u.username)})" if u.username else "")
        if admin_id is not None:
            head = "🩸 <b>FIRST BLOOD!</b>" if place == 1 else "🏆 <b>Flag topshirildi!</b>"
            try:
                await m.bot.send_message(
                    admin_id,
                    f"{head}\n👤 {who}, ID: <code>{u.id}</code>\n🏅 {place}-o'rin · {pts} ball\n"
                    f"🕐 {now:%d.%m.%Y %H:%M:%S}",
                )
            except Exception as e:  # admin botga /start bosmagan bo'lsa ham o'quvchiga ta'sir qilmasin
                logging.warning("adminga xabar yuborilmadi: %s", type(e).__name__)
        if place == 1 and announce_id is not None:
            try:
                await m.bot.send_message(announce_id, f"🩸 <b>FIRST BLOOD!</b> 🩸\n\n{who} birinchi bo'lib yechdi! 🔥")
            except Exception as e:
                logging.warning("e'lon yuborilmadi: %s", type(e).__name__)

    @dp.message()
    async def other(m: Message) -> None:
        await m.answer(TEXTS["wrong"])

    return dp


def chat_id(name: str) -> int | None:
    v = os.environ.get(name, "").strip()
    return int(v) if v.lstrip("-").isdigit() else None


async def main() -> None:
    token = os.environ.get("CHECKER_TOKEN")
    if not token:
        sys.exit("CHECKER_TOKEN o'rnatilmagan")
    raw = os.environ.get("FLAGS") or os.environ.get("FLAG") or ""
    flags = {f.strip() for f in raw.split("|") if f.strip()}
    if not flags:
        sys.exit("FLAG (yoki FLAGS) o'rnatilmagan")
    admin_id, announce_id = chat_id("ADMIN_CHAT_ID"), chat_id("ANNOUNCE_CHAT_ID")
    logging.basicConfig(level=logging.INFO)
    if admin_id is None:
        logging.warning("ADMIN_CHAT_ID yo'q: xabarlar yuborilmaydi, reyting qayta ishga tushganda yo'qoladi")

    bot = Bot(token, default=DefaultBotProperties(parse_mode="HTML"))
    store = Store(bot, admin_id)
    await store.load()
    dp = build(flags, admin_id, announce_id, store)

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

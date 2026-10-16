"""Yuvvosh Mushukcha boti (aiogram 3).

Ishga tushirish:
    export BOT_TOKEN=123456:ABC...      # BotFather bergan token
    export FLAG='...'                    # ixtiyoriy: config.json dagi flag o'rniga
    export SECRET_WORDS='soz1,soz2'    # ixtiyoriy: config.json dagi so'zlar o'rniga
    export RUN_SECONDS=20700             # ixtiyoriy: shuncha soniyadan keyin o'zi to'xtaydi
    python bot.py config.json

Xatti-harakati:
    /start          -> salomlashish
    /help           -> video + "yordam kutma" matni
    maxfiy so'z     -> flag
    boshqa hamma narsa -> 7 ta GIF+matn navbat bilan (1,2,...,7,1,2,...),
                          har bir foydalanuvchi uchun alohida hisoblanadi
"""

import asyncio
import html
import json
import logging
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.types import FSInputFile, Message

APOSTROPHES = re.compile(r"[ʻʼ‘’`´']")


def normalize(text: str) -> str:
    """Katta-kichik harf, apostrof va tinish belgilariga e'tibor bermaymiz."""
    text = APOSTROPHES.sub("", text.strip().lower())
    return re.sub(r"[^\w]+", "", text)


def media(base: Path, value: str | None):
    """Fayl bo'lsa uni, http(s) havola bo'lsa havolani qaytaradi; topilmasa None (faqat matn)."""
    if not value:
        return None
    if value.startswith(("http://", "https://")):
        return value
    path = base / value
    if path.is_file():
        return FSInputFile(path)
    logging.warning("media topilmadi, faqat matn yuboriladi: %s", path)
    return None


def build(cfg: dict, base: Path) -> Dispatcher:
    secrets = {normalize(s) for s in cfg["secret_words"]}
    texts = cfg["texts"]
    replies = cfg["wrong_replies"]
    counters: dict[int, int] = defaultdict(int)  # user_id -> nechta noto'g'ri javob
    dp = Dispatcher()

    async def send(m: Message, kind: str, file_value: str | None, caption: str) -> None:
        file = media(base, file_value)
        if file is None:
            await m.answer(caption)
        elif kind == "video":
            await m.answer_video(file, caption=caption)
        else:
            await m.answer_animation(file, caption=caption)

    @dp.message(CommandStart())
    async def start(m: Message) -> None:
        name = html.escape(m.from_user.first_name or "jigar")
        await m.answer(texts["start"].format(name=name))

    @dp.message(Command("help"))
    async def help_(m: Message) -> None:
        await send(m, "video", cfg.get("help_media"), texts["help"])

    @dp.message()
    async def anything(m: Message) -> None:
        if m.text and normalize(m.text) in secrets:
            logging.info("solved user_id=%s", m.from_user.id)
            caption = texts["correct"].format(flag=html.escape(cfg["flag"]))
            await send(m, "video", cfg.get("flag_media"), caption)
            return
        uid = m.from_user.id
        reply = replies[counters[uid] % len(replies)]
        counters[uid] += 1
        await send(m, "animation", reply.get("gif"), reply["text"])

    return dp


async def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    token = os.environ.get("BOT_TOKEN")
    if not token:
        sys.exit("BOT_TOKEN muhit o'zgaruvchisi o'rnatilmagan")
    cfg_path = Path(sys.argv[1])
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    # Maxfiy qiymatlar muhit o'zgaruvchilaridan (GitHub Secrets) ham berilishi mumkin
    if os.environ.get("FLAG"):
        cfg["flag"] = os.environ["FLAG"]
    if os.environ.get("SECRET_WORDS"):
        cfg["secret_words"] = [w.strip() for w in os.environ["SECRET_WORDS"].split(",") if w.strip()]
    if not cfg.get("flag") or not cfg.get("secret_words"):
        sys.exit("flag yoki secret_words berilmagan (config.json yoki FLAG / SECRET_WORDS)")
    logging.basicConfig(level=logging.INFO)
    dp = build(cfg, cfg_path.parent)
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

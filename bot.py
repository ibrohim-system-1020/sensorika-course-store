import os, asyncio
from dotenv import load_dotenv
load_dotenv()

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ChatJoinRequest
from db import connect, init_db
from telegram_api import revoke_link

TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL_ID = int(os.getenv("PRIVATE_CHANNEL_ID", "0") or 0)

dp = Dispatcher()

@dp.message(F.text == "/start")
async def start(message: Message):
    await message.answer(
        "Sensorika Course Store botiga xush kelibsiz!\n\n"
        f"Sizning Telegram ID: {message.from_user.id}\n"
        "Saytda ro‘yxatdan o‘tishda shu ID ni kiriting."
    )

@dp.message(F.text == "/id")
async def my_id(message: Message):
    await message.answer(f"Telegram ID: {message.from_user.id}")

@dp.chat_join_request()
async def join_request(req: ChatJoinRequest, bot: Bot):
    if CHANNEL_ID and req.chat.id != CHANNEL_ID:
        return
    invite = req.invite_link.invite_link if req.invite_link else None
    con = connect()
    order = con.execute("""
        SELECT o.id FROM orders o JOIN users u ON u.id=o.user_id
        WHERE o.status='paid' AND o.invite_link=? AND u.telegram_id=? AND o.used_at IS NULL
        ORDER BY o.id DESC LIMIT 1
    """, (invite, req.from_user.id)).fetchone()
    if order:
        await bot.approve_chat_join_request(req.chat.id, req.from_user.id)
        con.execute("UPDATE orders SET used_at=CURRENT_TIMESTAMP WHERE id=?", (order["id"],))
        con.commit()
        try: revoke_link(invite)
        except Exception: pass
    else:
        await bot.decline_chat_join_request(req.chat.id, req.from_user.id)
    con.close()

async def main():
    if not TOKEN:
        raise SystemExit("BOT_TOKEN .env faylida kiritilmagan")
    init_db()
    bot = Bot(TOKEN)
    await dp.start_polling(bot, allowed_updates=["message", "chat_join_request"])

if __name__ == "__main__":
    asyncio.run(main())

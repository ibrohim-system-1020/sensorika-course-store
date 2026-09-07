import os
from datetime import datetime, timedelta, timezone
import httpx

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
PRIVATE_CHANNEL_ID = os.getenv("PRIVATE_CHANNEL_ID", "")


def configured() -> bool:
    return bool(BOT_TOKEN and PRIVATE_CHANNEL_ID)


def create_join_link(name: str) -> str | None:
    if not configured():
        return None
    expire = int((datetime.now(timezone.utc) + timedelta(minutes=30)).timestamp())
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/createChatInviteLink"
    payload = {
        "chat_id": PRIVATE_CHANNEL_ID,
        "name": name[:32],
        "expire_date": expire,
        "creates_join_request": True,
    }
    r = httpx.post(url, json=payload, timeout=15)
    r.raise_for_status()
    return r.json()["result"]["invite_link"]


def send_message(chat_id: int, text: str):
    if not BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    httpx.post(url, json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True}, timeout=15)


def revoke_link(invite_link: str):
    if not configured() or not invite_link:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/revokeChatInviteLink"
    httpx.post(url, json={"chat_id": PRIVATE_CHANNEL_ID, "invite_link": invite_link}, timeout=15)

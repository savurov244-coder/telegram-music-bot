import os
import re
import asyncio
import tempfile
from pathlib import Path

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait, MessageNotModified

import yt_dlp

# ==================== KONFIGURATSIYA ====================
API_ID = 34584412 
API_HASH = "3aa0cabec466727017e6770381a68102"
BOT_TOKEN = "8349584164:AAGtmvoHrmo-g9bFMF4eenZpoHJspR95VZ8"

# Vaqtinchalik papka
TEMP_DIR = Path(tempfile.gettempdir()) / "music_bot_temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# yt-dlp sozlamalari
YDL_OPTS_BASE = {
    "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
    "outtmpl": str(TEMP_DIR / "%(id)s.%(ext)s"),
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "geo_bypass": True,
    "nocheckcertificate": True,
    "prefer_insecure": True,
}

# ==================== YORDAMCHI FUNKSIYALAR ====================

def is_url(text: str) -> bool:
    """Matn URL ekanligini tekshiradi"""
    url_pattern = re.compile(
        r'https?://(?:www\.)?(?:youtube\.com|youtu\.be|instagram\.com|tiktok\.com|vm\.tiktok\.com|music\.youtube\.com|m\.youtube\.com)/[^\s]+',
        re.IGNORECASE
    )
    return bool(url_pattern.search(text))


async def download_audio(query: str, is_search: bool = False) -> tuple[str, str, int]:
    """Audio yuklab oladi"""
    opts = YDL_OPTS_BASE.copy()

    if is_search:
        search_query = f"ytsearch1:{query}"
    else:
        search_query = query

    loop = asyncio.get_event_loop()

    def _download():
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(search_query, download=True)

            if not info:
                raise Exception("Qo'shiq topilmadi.")

            if "entries" in info:
                entries = info["entries"]
                if not entries:
                    raise Exception("Qidiruv natijasi bo'sh.")
                info = entries[0]

            filename = ydl.prepare_filename(info)

            if not os.path.exists(filename):
                base = os.path.splitext(filename)[0]
                for ext in [".m4a", ".webm", ".opus", ".ogg", ".mp3", ".mp4"]:
                    possible = base + ext
                    if os.path.exists(possible):
                        filename = possible
                        break

            title = info.get("title") or info.get("fulltitle") or "Unknown Track"
            duration = info.get("duration") or 0

            return filename, title, int(duration)

    return await loop.run_in_executor(None, _download)

async def safe_send_audio(client: Client, chat_id: int, file_path: str, title: str, duration: int, message: Message):
    """Audio yuboradi va faylni o'chiradi"""
    try:
        caption = f"🎵 **{title}**\n\n⏱ Davomiyligi: `{duration // 60}:{duration % 60:02d}`"

        await client.send_audio(
            chat_id=chat_id,
            audio=file_path,
            title=title[:64],
            performer="Music Bot",
            duration=duration if duration > 0 else None,
            caption=caption,
            parse_mode=ParseMode.MARKDOWN,
            reply_to_message_id=message.id
        )
    except Exception:
        await client.send_document(
            chat_id=chat_id,
            document=file_path,
            caption=caption,
            parse_mode=ParseMode.MARKDOWN,
            reply_to_message_id=message.id
        )
    finally:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass


# ==================== BOT ====================

app = Client(
    "MusicBotSession",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)


# ---------- /start komandasi va pastki tugmalar ----------
@app.on_message(filters.command("start"))
async def start_handler(client: Client, message: Message):
    user_name = message.from_user.first_name
    
    # Asosiy menyu tugmalari (ReplyKeyboardMarkup)
    main_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Bot haqida")],
            [KeyboardButton(text="Biz bilan bog'lanish")]
        ],
        resize_keyboard=True
    )

    text = (
        f"Hello, {user_name}!\n\n"
        "**Что умеет этот бот?**\n"
        "Qo'shiqni nomi yoki link yuboring"
    )
    await message.reply_text(text, reply_markup=main_keyboard, parse_mode=ParseMode.MARKDOWN)


# ---------- "Bot haqida" tugmasi bosilganda ----------
@app.on_message(filters.text & (filters.regex("^Bot haqida$")))
async def about_bot_handler(client: Client, message: Message):
    await message.reply_text("bu yerda istalgan qo'shig'ingizni bir necha soniyada topishingiz mumkin")


# ---------- "Biz bilan bog'lanish" tugmasi bosilganda ----------
@app.on_message(filters.text & (filters.regex("^Biz bilan bog'lanish$")))
async def contact_us_handler(client: Client, message: Message):
    inline_markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Profilga o'tish ✍️", url="https://t.me/Savurov_Umid")]
        ]
    )
    await message.reply_text("https://t.me/Savurov_Umid", reply_markup=inline_markup)


# ---------- Asosiy xabar handleri (Qo'shiq qidirish va link orqali yuklash) ----------
@app.on_message(filters.text & ~filters.command("start") & ~filters.regex("^Bot haqida$") & ~filters.regex("^Biz bilan bog'lanish$"))
async def main_handler(client: Client, message: Message):
    text = message.text.strip()

    if not text:
        return

    status_msg = await message.reply_text("🔍 Qidirilmoqda...", quote=True)

    try:
        is_link = is_url(text)

        if is_link:
            await status_msg.edit_text("⬇️ Link tahlil qilinmoqda va audio yuklanmoqda...")
            file_path, title, duration = await download_audio(text, is_search=False)
        else:
            await status_msg.edit_text("🔍 Qo'shiq qidirilmoqda...")
            file_path, title, duration = await download_audio(text, is_search=True)

        if not file_path or not os.path.exists(file_path):
            await status_msg.edit_text("❌ Audio topilmadi yoki yuklab bo'lmadi.")
            return

        file_size = os.path.getsize(file_path)
        if file_size > 49 * 1024 * 1024:
            os.remove(file_path)
            await status_msg.edit_text("❌ Fayl hajmi juda katta (50 MB dan oshiq).")
            return

        await status_msg.edit_text("📤 Yuborilmoqda...")
        await safe_send_audio(client, message.chat.id, file_path, title, duration, message)
        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: `{str(e)[:150]}`", parse_mode=ParseMode.MARKDOWN)


if __name__ == "__main__":
    print("Bot muvaffaqiyatli ishga tushdi...")
    app.run()
#!/usr/bin/env python3
"""
Avtotest Online Kurs — Telegram Bot
=====================================
Vazifalar:
  1. Yangi a'zo qo'shilganda shaxsiy xush kelibsiz xabari yuboradi
  2. Admin /dars buyrug'i bilan dars vaqtini qo'shadi
  3. Darsga 30 daqiqa qolganda guruhga eslatma yuboradi
"""

import logging
import json
import os
from datetime import datetime, timedelta

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Update, ChatMember
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ChatMemberHandler,
    ContextTypes,
)

# ═══════════════════════════════════════════════════════
#  SOZLAMALAR  —  faqat shu qatorlarni o'zgartiring
# ═══════════════════════════════════════════════════════

BOT_TOKEN   = "SIZNING_BOT_TOKENINGIZ"   # @BotFather dan
GURUH_ID    = -1001234567890              # guruh chat ID (manfiy son)
ADMIN_USERNAME = "@avtomentor_admin"      # admin username
TIMEZONE    = "Asia/Tashkent"
DARSLAR_FILE = "darslar.json"            # jadval saqlanadigan fayl

# ═══════════════════════════════════════════════════════
#  LOGGING
# ═══════════════════════════════════════════════════════

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

TZ = pytz.timezone(TIMEZONE)
scheduler = AsyncIOScheduler(timezone=TZ)

# ═══════════════════════════════════════════════════════
#  DARSLAR — JSON fayl orqali saqlash
# ═══════════════════════════════════════════════════════

def darslarni_yukla() -> list:
    if os.path.exists(DARSLAR_FILE):
        with open(DARSLAR_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []

def darslarni_saqla(darslar: list):
    with open(DARSLAR_FILE, "w", encoding="utf-8") as f:
        json.dump(darslar, f, ensure_ascii=False, indent=2)

# ═══════════════════════════════════════════════════════
#  XABARLAR SHABLONI
# ═══════════════════════════════════════════════════════

def xush_kelibsiz_xabari(ism: str) -> str:
    return (
        f"👋 Xush kelibsiz, <b>{ism}</b>!\n\n"
        f"Siz <b>Avtotest Online Kursiga</b> qo'shildingiz 🎉\n\n"
        f"📅 Kurs davomida <b>14 kun</b> sizga yordam berishga tayyormiz!\n\n"
        f"❓ Savol yoki muammo bo'lsa:\n"
        f"  • Guruhda yozing — hamkorlar yordam beradi\n"
        f"  • Adminga murojaat qiling: {ADMIN_USERNAME}\n\n"
        f"🚗 Muvaffaqiyatli o'qishlar!"
    )

def eslatma_xabari(dars_nomi: str, dars_vaqti: str) -> str:
    return (
        f"⏰ <b>Eslatma!</b>\n\n"
        f"📚 <b>{dars_nomi}</b> darsiga <b>30 daqiqa</b> qoldi!\n"
        f"🕐 Boshlanish vaqti: <b>{dars_vaqti}</b>\n\n"
        f"Tayyorlaning va o'z vaqtida ulaning 👆"
    )

# ═══════════════════════════════════════════════════════
#  YANGI A'ZO — avtomatik xush kelibsiz
# ═══════════════════════════════════════════════════════

async def yangi_avo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Guruhga yangi a'zo qo'shilganda ishlaydi."""
    natija = update.chat_member
    if natija is None:
        return

    # Faqat yangi qo'shilganlarni aniqlash
    eski_holat = natija.old_chat_member.status
    yangi_holat = natija.new_chat_member.status

    if eski_holat in (ChatMember.LEFT, ChatMember.BANNED) and \
       yangi_holat in (ChatMember.MEMBER, ChatMember.ADMINISTRATOR):

        foydalanuvchi = natija.new_chat_member.user
        ism = foydalanuvchi.full_name

        log.info(f"Yangi a'zo: {ism} (ID: {foydalanuvchi.id})")

        try:
            await ctx.bot.send_message(
                chat_id=GURUH_ID,
                text=xush_kelibsiz_xabari(ism),
                parse_mode="HTML",
            )
        except Exception as e:
            log.error(f"Xush kelibsiz xabar yuborishda xato: {e}")

# ═══════════════════════════════════════════════════════
#  ADMIN BUYRUQLARI
# ═══════════════════════════════════════════════════════

async def dars_qosh(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    /dars <sana> <vaqt> <dars nomi>
    Misol: /dars 2024-12-25 14:00 Python asoslari darsi
    """
    foydalanuvchi = update.effective_user
    chat = update.effective_chat

    # Faqat guruh adminlari ishlata oladi
    try:
        admin_info = await ctx.bot.get_chat_member(GURUH_ID, foydalanuvchi.id)
        if admin_info.status not in (ChatMember.ADMINISTRATOR, ChatMember.OWNER):
            await update.message.reply_text("❌ Bu buyruq faqat adminlar uchun!")
            return
    except Exception:
        await update.message.reply_text("❌ Tekshirishda xato. Bot guruhda admin bo'lishi kerak.")
        return

    if not ctx.args or len(ctx.args) < 3:
        await update.message.reply_text(
            "❗ <b>Foydalanish:</b>\n"
            "/dars 2024-12-25 14:00 Dars nomi\n\n"
            "<i>Misol: /dars 2024-12-25 14:00 Python asoslari</i>",
            parse_mode="HTML",
        )
        return

    sana_str  = ctx.args[0]   # 2024-12-25
    vaqt_str  = ctx.args[1]   # 14:00
    dars_nomi = " ".join(ctx.args[2:])

    try:
        dars_dt = datetime.strptime(f"{sana_str} {vaqt_str}", "%Y-%m-%d %H:%M")
        dars_dt = TZ.localize(dars_dt)
    except ValueError:
        await update.message.reply_text(
            "❌ Sana yoki vaqt formati noto'g'ri!\n"
            "To'g'ri format: <b>YYYY-MM-DD HH:MM</b>\n"
            "Misol: 2024-12-25 14:00",
            parse_mode="HTML",
        )
        return

    if dars_dt <= datetime.now(TZ):
        await update.message.reply_text("❌ O'tib ketgan vaqtni qo'shib bo'lmaydi!")
        return

    # Eslatma vaqti = dars boshlanishidan 30 daqiqa oldin
    eslatma_dt = dars_dt - timedelta(minutes=30)

    # Saqlash
    darslar = darslarni_yukla()
    dars_id = f"dars_{int(dars_dt.timestamp())}"
    darslar.append({
        "id": dars_id,
        "nomi": dars_nomi,
        "vaqt": dars_dt.isoformat(),
        "eslatma_vaqt": eslatma_dt.isoformat(),
    })
    darslarni_saqla(darslar)

    # Schedulerga qo'shish
    if eslatma_dt > datetime.now(TZ):
        scheduler.add_job(
            eslatma_yuborish,
            trigger="date",
            run_date=eslatma_dt,
            args=[ctx.bot, dars_nomi, dars_dt.strftime("%H:%M")],
            id=dars_id,
            replace_existing=True,
        )

    await update.message.reply_text(
        f"✅ <b>Dars qo'shildi!</b>\n\n"
        f"📚 Dars: <b>{dars_nomi}</b>\n"
        f"🕐 Boshlanish: <b>{dars_dt.strftime('%Y-%m-%d %H:%M')}</b>\n"
        f"⏰ Eslatma: <b>{eslatma_dt.strftime('%H:%M')}</b> da yuboriladi",
        parse_mode="HTML",
    )

async def darslar_royxati(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/darslar — barcha rejalashtirilgan darslar ro'yxati."""
    darslar = darslarni_yukla()
    hozir = datetime.now(TZ)

    kelgusi = [
        d for d in darslar
        if datetime.fromisoformat(d["vaqt"]) > hozir
    ]

    if not kelgusi:
        await update.message.reply_text("📭 Hozircha rejalashtirilgan dars yo'q.")
        return

    qatorlar = ["📅 <b>Kelgusi darslar:</b>\n"]
    for i, d in enumerate(sorted(kelgusi, key=lambda x: x["vaqt"]), 1):
        dt = datetime.fromisoformat(d["vaqt"])
        qatorlar.append(
            f"{i}. 📚 <b>{d['nomi']}</b>\n"
            f"   🕐 {dt.strftime('%Y-%m-%d %H:%M')}\n"
            f"   🆔 ID: <code>{d['id']}</code>"
        )

    await update.message.reply_text("\n\n".join(qatorlar), parse_mode="HTML")

async def dars_ochir(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/ochir <dars_id> — darsni o'chirish."""
    foydalanuvchi = update.effective_user
    try:
        admin_info = await ctx.bot.get_chat_member(GURUH_ID, foydalanuvchi.id)
        if admin_info.status not in (ChatMember.ADMINISTRATOR, ChatMember.OWNER):
            await update.message.reply_text("❌ Faqat adminlar uchun!")
            return
    except Exception:
        return

    if not ctx.args:
        await update.message.reply_text("❗ Foydalanish: /ochir <dars_id>")
        return

    dars_id = ctx.args[0]
    darslar = darslarni_yukla()
    yangi_darslar = [d for d in darslar if d["id"] != dars_id]

    if len(yangi_darslar) == len(darslar):
        await update.message.reply_text("❌ Bunday ID li dars topilmadi.")
        return

    darslarni_saqla(yangi_darslar)

    if scheduler.get_job(dars_id):
        scheduler.remove_job(dars_id)

    await update.message.reply_text(f"✅ Dars o'chirildi: <code>{dars_id}</code>", parse_mode="HTML")

# ═══════════════════════════════════════════════════════
#  ESLATMA YUBORISH
# ═══════════════════════════════════════════════════════

async def eslatma_yuborish(bot, dars_nomi: str, dars_vaqti: str):
    """Scheduler tomonidan chaqiriladi — guruhga eslatma yuboradi."""
    try:
        await bot.send_message(
            chat_id=GURUH_ID,
            text=eslatma_xabari(dars_nomi, dars_vaqti),
            parse_mode="HTML",
        )
        log.info(f"Eslatma yuborildi: {dars_nomi}")
    except Exception as e:
        log.error(f"Eslatma yuborishda xato: {e}")

# ═══════════════════════════════════════════════════════
#  UMUMIY BUYRUQLAR
# ═══════════════════════════════════════════════════════

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 <b>Avtotest Online Kurs Boti</b>\n\n"
        "📌 <b>Admin buyruqlari:</b>\n"
        "  /dars 2024-12-25 14:00 Dars nomi — yangi dars qo'shish\n"
        "  /darslar — barcha rejalashtirilgan darslar\n"
        "  /ochir &lt;id&gt; — darsni o'chirish\n\n"
        "📌 <b>Hammaga ochiq:</b>\n"
        "  /darslar — kelgusi darslar ro'yxati\n"
        "  /yordam — qo'llanma",
        parse_mode="HTML",
    )

async def yordam(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ <b>Yordam kerakmi?</b>\n\n"
        f"Admin bilan bog'laning: {ADMIN_USERNAME}\n"
        "yoki guruhda savolingizni yozing 👇",
        parse_mode="HTML",
    )

# ═══════════════════════════════════════════════════════
#  SAQLANGAN DARSLARNI SCHEDULERGA YUKLASH
# ═══════════════════════════════════════════════════════

def saqlangan_darslarni_yukla(bot):
    """Bot qayta ishga tushganda eski darslarni schedulerga qo'shadi."""
    darslar = darslarni_yukla()
    hozir = datetime.now(TZ)
    qoshildi = 0

    for d in darslar:
        eslatma_dt = datetime.fromisoformat(d["eslatma_vaqt"])
        if eslatma_dt > hozir:
            dars_dt = datetime.fromisoformat(d["vaqt"])
            scheduler.add_job(
                eslatma_yuborish,
                trigger="date",
                run_date=eslatma_dt,
                args=[bot, d["nomi"], dars_dt.strftime("%H:%M")],
                id=d["id"],
                replace_existing=True,
            )
            qoshildi += 1

    log.info(f"Saqlangan {qoshildi} ta dars schedulerga yuklandi.")

# ═══════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Buyruqlar
    app.add_handler(CommandHandler("start",   start))
    app.add_handler(CommandHandler("yordam",  yordam))
    app.add_handler(CommandHandler("dars",    dars_qosh))
    app.add_handler(CommandHandler("darslar", darslar_royxati))
    app.add_handler(CommandHandler("ochir",   dars_ochir))

    # Yangi a'zo — chat_member event
    app.add_handler(ChatMemberHandler(yangi_avo, ChatMemberHandler.CHAT_MEMBER))

    # Saqlangan darslarni yuklash va schedulerni ishga tushirish
    saqlangan_darslarni_yukla(app.bot)
    scheduler.start()

    log.info("✅ Bot ishga tushdi!")
    app.run_polling(
        allowed_updates=["message", "chat_member"],
        drop_pending_updates=True,
    )

if __name__ == "__main__":
    main()

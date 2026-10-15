import os
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from io import BytesIO

from dotenv import load_dotenv
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
)
from telegram.constants import ChatMemberStatus
from telegram.error import TelegramError
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, filters
)

from storage import (
    init_db, get_user, set_user_channel, set_user_setting, create_feedback,
    add_feedback_photo, get_feedback, list_feedback, delete_feedback,
    delete_expired, export_user_excel, count_stats, list_user_ids
)

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)
BOT_NAME = os.getenv("BOT_DISPLAY_NAME", "NoxiQueen")
DELETE_CHECK_SECONDS = 300

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("noxiqueen")

# In-memory workflow state. Database persists records/settings; workflow is intentionally simple.
FLOW = {}
ALBUMS = {}
ALBUM_TASKS = {}


def main_menu(user_id: int):
    rows = [
        [InlineKeyboardButton("📝 Create New Feedback", callback_data="new")],
        [InlineKeyboardButton("📢 Connect My Channel", callback_data="connect")],
        [InlineKeyboardButton("⚡ Auto Post Settings", callback_data="autopost")],
        [InlineKeyboardButton("📊 My Feedback Records", callback_data="records")],
        [InlineKeyboardButton("📁 Download Excel", callback_data="excel")],
        [InlineKeyboardButton("🗑️ Auto Delete Settings", callback_data="delete_settings")],
        [InlineKeyboardButton("👤 My Account", callback_data="account"),
         InlineKeyboardButton("❓ Help", callback_data="help")]
    ]
    if OWNER_ID and user_id == OWNER_ID:
        rows.append([InlineKeyboardButton("👑 Owner Panel", callback_data="owner")])
    return InlineKeyboardMarkup(rows)


def back_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="home")]])


def mode_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ AUTO POST", callback_data="mode_auto"),
         InlineKeyboardButton("📤 MANUAL POST", callback_data="mode_manual")],
        [InlineKeyboardButton("❌ Cancel", callback_data="home")]
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "", user.full_name or "")
    await update.effective_message.reply_text(
        f"👑 Welcome to {BOT_NAME}!\n\n"
        "📸 Photos + Feedback ko album post mein badlein.\n"
        "⚡ Auto Post ya 📤 Manual Post choose karein.\n"
        "🗑️ Auto-delete default 24 hours hai (aap change kar sakte hain).\n\n"
        "Shuru karne ke liye option choose karein:",
        reply_markup=main_menu(user.id)
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    FLOW.pop(update.effective_user.id, None)
    await update.effective_message.reply_text("Cancelled.", reply_markup=main_menu(update.effective_user.id))


async def show_home(query, user_id):
    await query.edit_message_text(f"👑 {BOT_NAME}\n\nChoose an option:", reply_markup=main_menu(user_id))


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    user = get_user(uid, q.from_user.username or "", q.from_user.full_name or "")
    data = q.data

    if data == "home":
        FLOW.pop(uid, None)
        await show_home(q, uid)
    elif data == "new":
        FLOW[uid] = {"step": "photos", "photos": []}
        await q.edit_message_text(
            "📸 Ab photos bhejo. Multiple photos ek-ek karke ya album mein bhej sakte ho.\n"
            "Photos bhejne ke baad neeche Done dabao.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Done — Photos Complete", callback_data="photos_done")],
                                               [InlineKeyboardButton("❌ Cancel", callback_data="home")]])
        )
    elif data == "photos_done":
        flow = FLOW.get(uid)
        if not flow or flow.get("step") != "photos" or not flow.get("photos"):
            await q.edit_message_text("Pehle kam se kam 1 photo bhejo.", reply_markup=back_menu())
            return
        flow["step"] = "feedback"
        await q.edit_message_text("📝 Ab apna feedback text bhejo. (Max 900 characters recommended)")
    elif data == "connect":
        FLOW[uid] = {"step": "connect_channel"}
        await q.edit_message_text(
            "📢 Apne channel ka @username ya numeric Channel ID bhejo.\n\n"
            "Pehle bot ko apne channel mein Admin banao aur Post Messages permission do.\n"
            "Public channel ke liye @channelusername use kar sakte ho.",
            reply_markup=back_menu()
        )
    elif data == "autopost":
        enabled = bool(user["auto_post"])
        chan = user["channel"] or "Not connected"
        await q.edit_message_text(
            f"⚡ AUTO POST SETTINGS\n\nStatus: {'ON 🟢' if enabled else 'OFF 🔴'}\nChannel: {chan}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🟢 Enable Auto Post", callback_data="auto_on"),
                 InlineKeyboardButton("🔴 Disable Auto Post", callback_data="auto_off")],
                [InlineKeyboardButton("📢 Connect/Change Channel", callback_data="connect")],
                [InlineKeyboardButton("🔙 Main Menu", callback_data="home")]
            ])
        )
    elif data in ("auto_on", "auto_off"):
        enabled = 1 if data == "auto_on" else 0
        if enabled and not user["channel"]:
            await q.edit_message_text("Pehle channel connect karo.", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Connect Channel", callback_data="connect")],
                [InlineKeyboardButton("🔙 Main Menu", callback_data="home")]
            ]))
            return
        set_user_setting(uid, "auto_post", enabled)
        await q.edit_message_text(f"Auto Post {'ON 🟢' if enabled else 'OFF 🔴'} ho gaya.", reply_markup=back_menu())
    elif data == "records":
        rows = list_feedback(uid, limit=10)
        if not rows:
            await q.edit_message_text("Abhi koi feedback record nahi hai.", reply_markup=back_menu())
            return
        text = "📊 YOUR LATEST FEEDBACK\n\n"
        buttons = []
        for row in rows:
            text += f"#{row['id']} · {row['created_at']} · {row['status']} · {row['photo_count']} photo(s)\n"
            buttons.append([InlineKeyboardButton(f"🗑️ Delete #{row['id']}", callback_data=f"del_{row['id']}")])
        buttons.append([InlineKeyboardButton("🗑️ Delete All Old Records", callback_data="delete_old")])
        buttons.append([InlineKeyboardButton("🔙 Main Menu", callback_data="home")])
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    elif data.startswith("del_"):
        fid = int(data.split("_", 1)[1])
        ok = delete_feedback(fid, uid)
        await q.edit_message_text("Record deleted." if ok else "Record nahi mila.", reply_markup=back_menu())
    elif data == "delete_old":
        # Only records older than 24h are removed by this button; ask confirmation.
        await q.edit_message_text("24 ghante se purane apne feedback records delete karein?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirm Delete", callback_data="delete_old_confirm")],
                [InlineKeyboardButton("❌ Cancel", callback_data="records")]
            ]))
    elif data == "delete_old_confirm":
        n = delete_expired(uid=uid, force_hours=24)
        await q.edit_message_text(f"🗑️ {n} purane record(s) delete kiye.", reply_markup=back_menu())
    elif data == "excel":
        bio = export_user_excel(uid)
        if not bio:
            await q.edit_message_text("Excel banane ke liye abhi records nahi hain.", reply_markup=back_menu())
            return
        bio.name = f"noxiqueen_feedback_{uid}.xlsx"
        await q.message.reply_document(document=bio, caption="📁 Aapke Feedback Records")
    elif data == "delete_settings":
        user = get_user(uid)
        hours = int(user["delete_hours"])
        enabled = bool(user["auto_delete"])
        await q.edit_message_text(
            f"🗑️ AUTO DELETE SETTINGS\n\nStatus: {'ON 🟢' if enabled else 'OFF 🔴'}\n"
            f"Timer: {hours} hour(s)\nDefault: 24 hours",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🟢 Auto Delete ON", callback_data="delete_on"),
                 InlineKeyboardButton("🔴 Auto Delete OFF", callback_data="delete_off")],
                [InlineKeyboardButton("24 Hours", callback_data="timer_24"),
                 InlineKeyboardButton("3 Days", callback_data="timer_72")],
                [InlineKeyboardButton("7 Days", callback_data="timer_168"),
                 InlineKeyboardButton("15 Days", callback_data="timer_360")],
                [InlineKeyboardButton("30 Days", callback_data="timer_720")],
                [InlineKeyboardButton("🔙 Main Menu", callback_data="home")]
            ])
        )
    elif data in ("delete_on", "delete_off"):
        set_user_setting(uid, "auto_delete", 1 if data == "delete_on" else 0)
        await q.edit_message_text(f"Auto Delete {'ON' if data == 'delete_on' else 'OFF'} ho gaya.", reply_markup=back_menu())
    elif data.startswith("timer_"):
        hours = int(data.split("_")[1])
        set_user_setting(uid, "delete_hours", hours)
        await q.edit_message_text(f"Auto Delete timer {hours} hours set ho gaya.", reply_markup=back_menu())
    elif data == "account":
        user = get_user(uid)
        await q.edit_message_text(
            f"👤 MY ACCOUNT\n\nUser ID: {uid}\nChannel: {user['channel'] or 'Not connected'}\n"
            f"Auto Post: {'ON' if user['auto_post'] else 'OFF'}\n"
            f"Auto Delete: {'ON' if user['auto_delete'] else 'OFF'} ({user['delete_hours']}h)",
            reply_markup=back_menu()
        )
    elif data == "help":
        await q.edit_message_text(
            "❓ HELP\n\n1. Create New Feedback dabao.\n2. Photos bhejo aur Done dabao.\n"
            "3. Feedback text bhejo.\n4. Auto ya Manual mode choose karo.\n\n"
            "Auto Post ke liye bot ko channel admin aur Post Messages permission chahiye.\n"
            "Auto Delete sirf bot ke records/temporary data ko saaf karta hai; channel posts nahi hatata.",
            reply_markup=back_menu()
        )
    elif data in ("mode_auto", "mode_manual"):
        flow = FLOW.get(uid)
        if not flow or flow.get("step") != "mode":
            await q.edit_message_text("Session expire ho gaya. /start karke dobara try karo.", reply_markup=back_menu())
            return
        mode = "AUTO" if data == "mode_auto" else "MANUAL"
        user = get_user(uid)
        if mode == "AUTO" and not user["channel"]:
            await q.edit_message_text("Auto Post ke liye pehle channel connect karo.", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Connect Channel", callback_data="connect")],
                [InlineKeyboardButton("📤 Manual Mode", callback_data="mode_manual")]
            ]))
            return
        fid = create_feedback(uid, flow["feedback"], len(flow["photos"]), mode)
        photos = flow["photos"]
        status = "PENDING"
        try:
            if mode == "AUTO":
                await verify_channel_can_post(context, user["channel"])
                await send_album(context, user["channel"], photos, flow["feedback"])
                status = "POSTED"
                from storage import update_feedback_status
                update_feedback_status(fid, status, user["channel"])
                await q.edit_message_text(f"✅ Feedback #{fid} channel par post ho gaya aur record save ho gaya.", reply_markup=back_menu())
            else:
                await send_album(context, uid, photos, flow["feedback"])
                from storage import update_feedback_status
                update_feedback_status(fid, "MANUAL_SENT", "")
                await q.edit_message_text(
                    f"📤 Album aapko bhej diya gaya.\nFeedback ID: #{fid}\n"
                    "Ab aap ise apne channel par manually post kar sakte hain.\n\n"
                    "Note: Bot channel par post nahi karega.",
                    reply_markup=back_menu()
                )
        except TelegramError as e:
            from storage import update_feedback_status
            update_feedback_status(fid, "FAILED", user["channel"] if mode == "AUTO" else "")
            await q.edit_message_text(
                f"❌ Post nahi ho saka.\nReason: {str(e)[:300]}\n"
                "Channel ID/permissions check karo. Record FAILED mark kiya gaya hai.",
                reply_markup=back_menu()
            )
        FLOW.pop(uid, None)
    elif data == "owner":
        if not OWNER_ID or uid != OWNER_ID:
            await q.edit_message_text("Not authorized.", reply_markup=back_menu())
            return
        stats = count_stats()
        await q.edit_message_text(
            f"👑 OWNER PANEL\n\nUsers: {stats['users']}\nFeedback: {stats['feedback']}\n"
            f"Posted: {stats['posted']}\nPending/Other: {stats['other']}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 Export All Users", callback_data="owner_excel")],
                [InlineKeyboardButton("🔙 Main Menu", callback_data="home")]
            ])
        )
    elif data == "owner_excel":
        if not OWNER_ID or uid != OWNER_ID:
            await q.edit_message_text("Not authorized.", reply_markup=back_menu())
            return
        bio = export_user_excel(None)
        if bio:
            bio.name = "noxiqueen_all_feedback.xlsx"
            await q.message.reply_document(document=bio, caption="All Feedback Records (Owner only)")


async def verify_channel_can_post(context, channel):
    me = await context.bot.get_me()
    member = await context.bot.get_chat_member(chat_id=channel, user_id=me.id)
    if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
        raise TelegramError("Bot channel ka admin nahi hai.")
    if member.status == ChatMemberStatus.ADMINISTRATOR and not getattr(member, "can_post_messages", False):
        raise TelegramError("Bot ke paas Post Messages permission nahi hai.")


async def send_album(context, chat_id, photos, feedback):
    # Telegram media groups support 2-10 items. Single photo uses send_photo.
    photos = photos[:10]
    if len(photos) == 1:
        await context.bot.send_photo(chat_id=chat_id, photo=photos[0], caption=feedback[:1024])
        return
    media = []
    for i, photo_id in enumerate(photos):
        if i == 0:
            media.append(InputMediaPhoto(media=photo_id, caption=feedback[:1024]))
        else:
            media.append(InputMediaPhoto(media=photo_id))
    await context.bot.send_media_group(chat_id=chat_id, media=media)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    flow = FLOW.get(uid)
    if not flow or flow.get("step") != "photos":
        await update.effective_message.reply_text("Naya Feedback banane ke liye /start dabao aur Create New Feedback choose karo.")
        return
    photo_id = update.effective_message.photo[-1].file_id
    if photo_id not in flow["photos"]:
        flow["photos"].append(photo_id)
    await update.effective_message.reply_text(f"📸 Photo add ho gayi. Total: {len(flow['photos'])}\nAur bhejo ya Done dabao.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = (update.effective_message.text or "").strip()
    flow = FLOW.get(uid)
    if not flow:
        await update.effective_message.reply_text("Menu ke liye /start dabao.", reply_markup=main_menu(uid))
        return
    if flow.get("step") == "feedback":
        if len(text) > 900:
            await update.effective_message.reply_text("Feedback 900 characters se chhota rakho, phir dobara bhejo.")
            return
        flow["feedback"] = text
        flow["step"] = "mode"
        await update.effective_message.reply_text(
            "Feedback ready hai. Posting mode choose karo:",
            reply_markup=mode_menu()
        )
    elif flow.get("step") == "connect_channel":
        channel = text
        if not (channel.startswith("@") or channel.startswith("-100") or channel.lstrip("-").isdigit()):
            await update.effective_message.reply_text("Channel ka @username ya numeric ID bhejo.")
            return
        try:
            chat = await context.bot.get_chat(channel)
            me = await context.bot.get_me()
            member = await context.bot.get_chat_member(chat_id=chat.id, user_id=me.id)
            if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
                await update.effective_message.reply_text("Bot ko pehle channel mein Admin banao aur Post Messages permission do.")
                return
            set_user_channel(uid, str(chat.id))
            await update.effective_message.reply_text(
                f"✅ Channel connect ho gaya: {chat.title or chat.username or chat.id}\nChannel ID saved.",
                reply_markup=main_menu(uid)
            )
            FLOW.pop(uid, None)
        except TelegramError as e:
            await update.effective_message.reply_text(
                "❌ Channel connect nahi hua. Check karo: channel ID/@username sahi hai aur bot admin hai.\n"
                f"Details: {str(e)[:250]}"
            )
    else:
        await update.effective_message.reply_text("Current step ke liye button use karo ya /cancel bhejo.")


async def cleanup_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        count = delete_expired()
        if count:
            log.info("Auto-deleted %s expired feedback records", count)
    except Exception:
        log.exception("Cleanup job failed")


async def post_init(application: Application):
    init_db()
    application.job_queue.run_repeating(cleanup_job, interval=DELETE_CHECK_SECONDS, first=30)
    log.info("%s bot started", BOT_NAME)


def main():
    if not TOKEN or TOKEN == "PUT_YOUR_BOT_TOKEN_HERE":
        raise SystemExit("Set BOT_TOKEN in .env before running.")
    application = Application.builder().token(TOKEN).post_init(post_init).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CallbackQueryHandler(callback_router))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

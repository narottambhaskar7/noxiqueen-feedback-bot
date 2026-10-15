# NoxiQueen Gaming Post Bot

Telegram bot for creating BGMI/PUBG posts from separate photos (no collage), with caption templates, preview, channel auto-post/manual-ready flow, and post-history management.

## Features
- Create a post from 1–10 photos. Photos remain separate in a Telegram album.
- Latest photo acknowledgement includes **➕ More Photos** and **✅ Done** buttons.
- Write your own caption or select a built-in BGMI/PUBG gaming caption style.
- Preview album and caption before choosing Auto Post or Manual Post.
- Connect a channel by public `@username`, numeric chat ID, or public `https://t.me/username` link.
- Attempt channel auto-detection when Telegram sends a bot-admin status update.
- View the latest 10 post-history records and delete all of your saved history records.
- No broadcast system and no thumbnail maker.

## Setup
1. Install Python 3.10+.
2. Run `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env`.
4. Set `BOT_TOKEN` from @BotFather. Keep it private. `OWNER_ID` is optional and must be your numeric Telegram user ID for auto-connect.
5. Run `python bot.py`.

## Connect channel
Add the bot to your Telegram channel as an administrator and enable **Post Messages**. If Telegram sends the bot's `my_chat_member` update and `OWNER_ID` is configured, the bot attempts to auto-connect that channel for the owner. Otherwise use **Connected Channel → Connect by username/ID**. Public channel links are supported; private invite links cannot reliably identify a channel for this connect flow, so use its numeric chat ID where available.

## Storage and deletion notes
- The bot does **not** save image files permanently on its own server. During an unfinished draft, Telegram `file_id` values are held in RAM; the history database stores caption, photo count, status, channel, and timestamps, not the actual image bytes.
- Telegram itself hosts media sent through Telegram. This bot cannot globally erase Telegram's hosted copies or remove photos from a user's chat history.
- **Delete All History** deletes saved history rows from this bot's SQLite database only. It does not delete already-published channel posts. Deleting channel posts requires storing their message IDs and the bot having suitable permissions; that is not implemented in this version.
- The unfinished draft is in memory; restarting the bot interrupts an unfinished draft. Saved history rows persist in SQLite.
- Telegram albums support up to 10 photos.
- Generated captions use built-in templates; no external AI API is required.
- Keep only one polling instance running with the same bot token.

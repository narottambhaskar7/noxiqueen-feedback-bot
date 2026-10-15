# NoxiQueen Gaming Post Bot

Telegram bot for making BGMI/PUBG gaming posts from separate photos (no collage), with caption templates, preview, channel auto-post/manual-ready flow.

## Features
- Create a post from 1–10 photos. Photos remain separate in a Telegram album.
- Write your own caption or select a generated BGMI/PUBG caption style.
- Preview album and caption before posting.
- Auto-post to the connected Telegram channel, or choose Manual Post to keep the preview ready for manual posting.
- Auto-detect a channel when the bot receives a channel-admin status update. Set `OWNER_ID` to your numeric Telegram user ID for auto-connect.
- `/start` and `/cancel` commands.

## Setup
1. Install Python 3.10+.
2. Run `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env`.
4. Set `BOT_TOKEN` to the token from @BotFather. Keep it private. `OWNER_ID` is optional; use your numeric Telegram user ID.
5. Run `python bot.py`.

## Connect channel
Add the bot to your Telegram channel as an administrator and enable **Post Messages**. If Telegram sends the bot's `my_chat_member` update and `OWNER_ID` is configured, the bot attempts to auto-connect that channel for the owner. If auto-detection does not trigger, use **Connected Channel → Connect by username/ID** in the bot.

## Important limitations
- The bot can only post to channels where it has admin rights and Post Messages permission.
- Telegram media albums support up to 10 photos.
- Generated captions use built-in templates; no external AI API is required.
- The in-progress photo/caption workflow is held in memory; a restart interrupts an unfinished draft. SQLite feedback records persist.
- For hosting, keep only one polling instance running with the same bot token.

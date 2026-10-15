# NoxiQueen Telegram Feedback Bot

A starter Python Telegram bot for multi-user feedback posts, photo albums, channel posting, Excel export, and automatic expiry of bot-side feedback records.

## Security first
- Never put your bot token into source code or share it in chat.
- Create `.env` from `.env.example` and keep it private.
- Since a token was shared previously, use the newly regenerated token only.
- Set `OWNER_ID` to your numeric Telegram user ID to enable the owner panel.
- The Owner panel export contains other users' records; protect owner access and hosting credentials.

## Features in this starter
- `/start` menu and `/cancel`
- Users can create a feedback by sending photos, pressing Done, then sending feedback text
- AUTO mode posts the album to the user's connected channel
- MANUAL mode sends the album back to the user
- Per-user channel connection and Auto Post setting
- Per-user Excel export
- Owner summary and all-record Excel export
- Auto-delete defaults to ON / 24 hours for each new user
- Users can change retention or turn Auto Delete off
- Scheduled cleanup deletes expired bot-side feedback rows
- Published Telegram channel posts are NOT deleted by default

## Important implementation notes
- Telegram albums support 2–10 media items. This starter accepts photo file IDs and sends at most the first 10 in an album. If only one photo is sent, it sends a single photo.
- Feedback is attached as the caption of the first photo.
- For reliability, send photos one at a time or as an album, then press **Done — Photos Complete**.
- Telegram may group incoming photos as one media group, but this starter collects each photo message as it arrives; duplicates are ignored.
- This starter stores the feedback text and photo count in SQLite. It does not persist Telegram file IDs in the database, so old records are for reporting rather than reconstructing an album later.
- Auto-delete removes records from the bot database. It does not delete messages already published in Telegram channels, nor does it revoke files already sent to a user.
- The Excel export reflects records currently present in the database. If records expire and are deleted, they will no longer appear in a future export. Download exports you need to keep before expiry.
- This is a starter project; test it with a private test channel before inviting public users. For production, add rate limits, abuse controls, persistent workflow state, backup strategy, and error monitoring.

## Run locally
1. Install Python 3.11+.
2. Extract this ZIP.
3. Copy `.env.example` to `.env`.
4. Edit `.env` and set `BOT_TOKEN`, `OWNER_ID`, and optional `DB_PATH`.
5. Install dependencies:
   ```bash
   python -m venv .venv
   # Windows: .venv\Scripts\activate
   # Linux/macOS: source .venv/bin/activate
   pip install -r requirements.txt
   ```
6. Start:
   ```bash
   python bot.py
   ```

## Cloud deployment
Use a Python-capable host that explicitly permits long-running background workers, or a VPS. Upload the files, set environment variables securely, install `requirements.txt`, and run `python bot.py` under the provider's process manager or `systemd`. Do not assume ordinary shared cPanel hosting permits a permanent bot process.

For channel posting, add the bot as an administrator in each user's channel and grant permission to post messages. Users should connect only channels they own/manage.

import os, logging, random, asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.constants import ChatMemberStatus
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ChatMemberHandler, ContextTypes, filters
from storage import init_db, get_user, set_user_channel, create_feedback, update_feedback_status, list_feedback, delete_all_feedback

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN', '').strip()
BOT_NAME = os.getenv('BOT_DISPLAY_NAME', 'NoxiQueen')
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
logging.getLogger('httpx').setLevel(logging.WARNING)
log = logging.getLogger('noxiqueen')
FLOW = {}
PHOTO_BATCH_TASKS = {}
PHOTO_BATCH_LOCKS = {}
ALBUMS = {}
ALBUM_TASKS = {}

CAPTIONS = {
 '🔥 Clutch & Highlights': [
  '🔥 CLUTCH MODE: ON! Last zone, full pressure, clean finish. 🎯',
  '⚡ One squad. One chance. TOTAL DOMINATION. 🏆',
  '🎯 Aim locked. Focus max. Highlight secured. 🔥',
  '💥 They pushed together, but they went back to lobby together.',
  '🏆 Calm hands, sharp aim, clutch finish. That is the play.',
  '🔥 Turning impossible fights into unforgettable highlights.',
  '🎮 One clean spray can change the whole match.',
  '⚔️ Outnumbered, not outplayed. Clutch secured!',
  '💯 No panic in the final circle. Just pure game sense.',
  '🚀 The kind of finish you replay twice!',
 ],
 '👑 Royal / Pro Player': [
  '👑 ROYAL GAMEPLAY — BUILT DIFFERENT. Skill speaks louder than words.',
  '🏆 No luck, just game sense. Welcome to the lobby!',
  '🎯 Consistency makes the difference. Another clean play.',
  '⚡ Play smart, move sharp, finish strong.',
  '👑 Lobby mein entry royal, exit legendary.',
  '🔥 Practice behind the scenes, confidence in the fight.',
  '💎 Clean movement. Clear calls. Solid teamwork.',
  '🏆 Every match is a chance to level up.',
  '🎮 Not just playing the game—reading the whole lobby.',
  '🚀 Pro mindset, fearless gameplay.',
 ],
 '💀 Intense Battle': [
  '💀 Every second counts. Every move matters. THE BATTLE IS ON!',
  '⚔️ Pressure rising. Enemies closing in. We do not back down.',
  '🔥 Final circle, full focus, zero hesitation.',
  '🎯 The fight got intense, but the squad stayed ready.',
  '💥 One decision. One push. One big moment.',
  '🚨 Danger close—time to lock in!',
  '🛡️ Hold the line, cover the squad, win the fight.',
  '⚡ Chaos around us, focus within us.',
  '🎮 Every footstep tells a story. Stay alert!',
  '🏁 The pressure was real. The finish was worth it.',
 ],
 '🌑 Dark Gaming': [
  '🌑 SILENT MOVES. DEADLY FINISH. The shadows belong to the skilled.',
  '🖤 No noise. No fear. Just precision.',
  '🌘 Quiet approach, loud result.',
  '💀 The dark lobby has a new highlight.',
  '⚫ Stay unseen, stay sharp, strike at the right time.',
  '🌑 Cold focus. Clean execution.',
  '🖤 The calmest player can make the loudest play.',
  '🎯 Shadows move. Targets fall. Highlight saved.',
  '🌒 Mystery in the movement, precision in the aim.',
  '⚡ Dark mode gameplay, bright scoreboard.',
 ],
 '😂 Funny Moments': [
  '😂 Plan: perfect. Execution: questionable. Result: CONTENT! 🤣',
  '🤣 Bro thought it was an easy lobby… surprise!',
  '🎮 My aim has two moods: pro and potato.',
  '😂 Squad said “trust me” … and then this happened.',
  '💀 Enemy confused, teammates laughing, clip saved.',
  '🤣 It was not a mistake. It was a surprise strategy.',
  '😂 When the plan works by pure accident.',
  '🎯 Aim loading… please wait!',
  '🤣 The lobby was serious until we arrived.',
  '🔥 100% confidence, 2% planning, 200% entertainment.',
 ],
 '🚀 Trending Gaming': [
  '🚀 NEW HIGHLIGHT DROP! Rate this play from 1–10 👇',
  '🔥 WATCH TILL THE END! This moment hits different.',
  '🎮 BGMI vibes, squad energy, unforgettable moments.',
  '💥 One clip, one story, one crazy finish!',
  '📸 Saving the moment, sharing the grind.',
  '⚡ If you blinked, you missed the best part!',
  '🏆 Another gaming memory added to the collection.',
  '🔥 Rate the gameplay and drop your favourite moment!',
  '🎯 Precision, patience, and a little bit of chaos.',
  '🚀 Fresh gameplay drop—show some love to the squad!',
 ]
}

def with_brand_hashtags(caption):
 tags = '#WalterBlack #BGMI #PUBGMobile #Gaming'
 if '#WalterBlack' not in caption:
  caption = caption.rstrip() + '\n\n' + tags
 return caption

def menu():
 return InlineKeyboardMarkup([[InlineKeyboardButton('🎮 Create Gaming Post', callback_data='new')], [InlineKeyboardButton('🗂️ Post History', callback_data='history')], [InlineKeyboardButton('📡 Connected Channel', callback_data='channel'), InlineKeyboardButton('❓ Help', callback_data='help')]])
def back(): return InlineKeyboardMarkup([[InlineKeyboardButton('🏠 Main Menu', callback_data='home')]])
def photo_buttons():
 return InlineKeyboardMarkup([[InlineKeyboardButton('➕ Add More Photos', callback_data='photos_more')], [InlineKeyboardButton('✅ Done — Next Step', callback_data='photos_done')], [InlineKeyboardButton('❌ Cancel', callback_data='home')]])
def caption_buttons():
 rows=[[InlineKeyboardButton('✍️ Write My Own Caption', callback_data='own_caption')],[InlineKeyboardButton('✨ Generate Gaming Caption', callback_data='auto_caption')],[InlineKeyboardButton('❌ Cancel', callback_data='home')]]
 return InlineKeyboardMarkup(rows)
def styles(): return InlineKeyboardMarkup([[InlineKeyboardButton(k, callback_data='style:'+k)] for k in CAPTIONS]+[[InlineKeyboardButton('🔙 Back', callback_data='caption_back')]])
def post_buttons(): return InlineKeyboardMarkup([[InlineKeyboardButton('⚡ AUTO POST', callback_data='post_auto')],[InlineKeyboardButton('📤 MANUAL POST', callback_data='post_manual')],[InlineKeyboardButton('🔁 Change Caption', callback_data='caption_back')],[InlineKeyboardButton('❌ Cancel', callback_data='home')]])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
 u=update.effective_user; get_user(u.id,u.username or '',u.full_name or '')
 await update.effective_message.reply_text(f'👑 Welcome to {BOT_NAME}!\n\nBGMI / PUBG photos bhejo, gaming caption banao, preview dekho aur Auto ya Manual Post choose karo.\n\nChannel auto-connect ke liye bot ko channel ka admin banao aur Post Messages permission do.',reply_markup=menu())
async def show_home(q, uid):
 FLOW.pop(uid,None); await q.edit_message_text(f'👑 {BOT_NAME}\n\nChoose an option:',reply_markup=menu())
async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
 q=update.callback_query; await q.answer(); uid=q.from_user.id; data=q.data
 u=get_user(uid,q.from_user.username or '',q.from_user.full_name or '')
 if data=='home': await show_home(q,uid); return
 if data=='history':
  rows = list_feedback(uid, limit=20)
  if not rows:
   await q.edit_message_text('🗂️ Abhi koi saved post history nahi hai.', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🗑️ Delete All History', callback_data='delete_history')],[InlineKeyboardButton('🏠 Main Menu', callback_data='home')]])); return
  lines = ['🗂️ YOUR POST HISTORY (latest 20)', '']
  for item in rows:
   stamp = str(item.get('created_at', ''))[:16].replace('T', ' ')
   lines.append(f"#{item['id']} · {item['status']} · {item['photo_count']} photo(s) · {stamp}")
  lines += ['', '⚠️ Yahan se history delete karne par sirf bot ke saved records delete honge. Channel ke posts nahi hatenge.']
  await q.edit_message_text('\n'.join(lines), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🗑️ Delete All History', callback_data='delete_history')],[InlineKeyboardButton('🏠 Main Menu', callback_data='home')]])); return
 if data=='delete_history':
  await q.edit_message_text('⚠️ Kya tum bot mein saved saari post/feedback history delete karna chahte ho?\n\nIsse sirf bot ki history clear hogi. Channel par published posts bilkul delete nahi hongi.', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('✅ Yes, Delete History', callback_data='confirm_delete_history')],[InlineKeyboardButton('❌ Cancel', callback_data='cancel_delete_history')]])); return
 if data=='confirm_delete_history':
  deleted = delete_all_feedback(uid)
  await q.edit_message_text(f'🗑️ Bot history clear ho gayi. {deleted} record(s) delete kiye.\n\nChannel ke posts ko touch nahi kiya gaya.', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🗂️ View History', callback_data='history')],[InlineKeyboardButton('🏠 Main Menu', callback_data='home')]])); return
 if data=='cancel_delete_history':
  rows = list_feedback(uid, limit=20)
  await q.edit_message_text(f'✅ Delete cancel kar diya. Tumhari history safe hai ({len(rows)} recent record(s)).', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🗂️ Post History', callback_data='history')],[InlineKeyboardButton('🏠 Main Menu', callback_data='home')]])); return
 if data=='new':
  FLOW[uid]={'step':'photos','photos':[],'caption':''}
  await q.edit_message_text('📸 Apni 1–10 photos bhejo (ek-ek karke ya Telegram album mein). Har photo add hone ke baad yahin Done dabana. Collage nahi banega—photos album mein separate rahengi.',reply_markup=photo_buttons()); return
 if data=='photos_done':
  f=FLOW.get(uid)
  if not f or f['step']!='photos':
   await q.edit_message_text('Photo session nahi mila. Main Menu se Create Gaming Post dobara shuru karo.',reply_markup=back()); return
  if not f['photos']:
   await q.edit_message_text('Pehle kam se kam ek photo bhejo, phir Done dabao.',reply_markup=photo_buttons()); return
  if (f.get('caption') or '').strip():
   f['step']='preview'
   await q.edit_message_text('✅ Photos complete. Photo ke saath diya gaya caption use kar raha hoon.')
   await send_preview(context,uid,f)
   await context.bot.send_message(chat_id=uid, text='👆 Preview ke neeche se next action choose karo:', reply_markup=post_buttons())
  else:
   f['step']='caption_choice'
   await q.edit_message_text('✅ Photos complete. Ab neeche caption option choose karo.')
   await context.bot.send_message(chat_id=uid, text='📝 Caption kaise banana hai?', reply_markup=caption_buttons())
  return
 if data=='photos_more':
  f=FLOW.get(uid)
  if not f or f.get('step')!='photos':
   await q.edit_message_text('Photo session expire ho gaya. Main Menu se dobara shuru karo.',reply_markup=back()); return
  await q.answer('Ab aur photos bhej sakte ho.')
  await q.message.reply_text(f'📸 Aur photos bhejo. Abhi {len(f["photos"])} / 10 hain.',reply_markup=photo_buttons())
  return
 if data=='own_caption':
  f=FLOW.get(uid)
  if not f: await q.edit_message_text('Session expire. /start dabao.',reply_markup=back()); return
  f['step']='own_caption'; await q.edit_message_text('Apna caption text bhejo. Caption 900 characters tak rakho.',reply_markup=back()); return
 if data=='auto_caption':
  f=FLOW.get(uid)
  if not f: await q.edit_message_text('Session expire. /start dabao.',reply_markup=back()); return
  f['step']='style'; await q.edit_message_text('🎮 Gaming caption style choose karo:',reply_markup=styles()); return
 if data=='caption_back':
  f=FLOW.get(uid)
  if not f: await q.edit_message_text('Session expire. /start dabao.',reply_markup=back()); return
  f['step']='caption_choice'; await q.edit_message_text('📝 Caption kaise banana hai?',reply_markup=caption_buttons()); return
 if data.startswith('style:'):
  f=FLOW.get(uid)
  if not f: await q.edit_message_text('Session expire. /start dabao.',reply_markup=back()); return
  f['caption']=with_brand_hashtags(random.choice(CAPTIONS.get(data[6:],CAPTIONS['🚀 Trending Gaming'])))
  f['step']='preview'; await q.edit_message_text('✅ Caption ready. Preview neeche bhej raha hoon.')
  await send_preview(context,uid,f)
  await context.bot.send_message(chat_id=uid, text='👆 Preview ke neeche se next action choose karo:', reply_markup=post_buttons()); return
 if data=='post_auto' or data=='post_manual':
  f=FLOW.get(uid)
  if not f or f.get('step')!='preview': await q.edit_message_text('Pehle post preview banao.',reply_markup=back()); return
  mode='AUTO' if data=='post_auto' else 'MANUAL'
  if mode=='AUTO':
   user=get_user(uid)
   if not user.get('channel'):
    await q.edit_message_text('❌ Channel connected nahi hai. Bot ko channel admin banao; phir /start karke Connected Channel check karo.',reply_markup=back()); return
   try:
    await verify_channel(context,user['channel']); await send_album(context,user['channel'],f['photos'],f['caption'])
    fid=create_feedback(uid,f['caption'],len(f['photos']),'AUTO'); update_feedback_status(fid,'POSTED',str(user['channel']))
    FLOW.pop(uid,None); await q.edit_message_text('✅ Post channel par publish ho gayi!',reply_markup=back())
   except TelegramError as e: await q.edit_message_text(f'❌ Post nahi ho saki: {str(e)[:250]}\nBot admin aur Post Messages permission check karo.',reply_markup=post_buttons())
  else:
   # Preview already delivered to the user, so no duplicate album is sent.
   fid=create_feedback(uid,f['caption'],len(f['photos']),'MANUAL'); update_feedback_status(fid,'MANUAL_READY','')
   FLOW.pop(uid,None); await q.edit_message_text(f'📤 Manual post ready hai. Upar jo preview album aur caption mila hai, use apne channel par manually forward/post kar sakte ho.\nID: #{fid}',reply_markup=back())
  return
 if data=='channel':
  user=get_user(uid); await q.edit_message_text('📡 CHANNEL STATUS\n\n'+('Connected channel ID: '+str(user['channel']) if user.get('channel') else 'Abhi channel connect nahi hai.')+'\n\nBot ko channel mein admin banao aur Post Messages permission do. Auto-detection na ho to Connect by username/ID dabao ya /connect @channelusername bhejo.',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔗 Connect by username/ID',callback_data='connect')],[InlineKeyboardButton('🏠 Main Menu',callback_data='home')]])); return
 if data=='connect':
  FLOW[uid]={'step':'connect'}; await q.edit_message_text('Channel ka @username ya numeric ID bhejo. Bot pehle se channel admin hona chahiye aur Post Messages permission honi chahiye.',reply_markup=back()); return
 if data=='help':
  await q.edit_message_text('1) Create Gaming Post\n2) Photos bhejo, Done dabao\n3) Apna ya generated BGMI/PUBG caption choose karo\n4) Preview dekho\n5) Auto Post ya Manual Post choose karo.\n\nAuto Post ke liye bot channel admin + Post Messages permission zaroori hai. ',reply_markup=back()); return

async def send_preview(context,uid,f):
 await send_album(context,uid,f['photos'],f['caption'])
async def send_album(context,chat_id,photos,caption):
 photos=photos[:10]
 if len(photos)==1: await context.bot.send_photo(chat_id,photos[0],caption=caption[:1024]); return
 media=[InputMediaPhoto(media=p,caption=caption[:1024] if i==0 else None) for i,p in enumerate(photos)]
 await context.bot.send_media_group(chat_id=chat_id,media=media)
async def verify_channel(context,channel):
 me=await context.bot.get_me(); m=await context.bot.get_chat_member(chat_id=channel,user_id=me.id)
 status = getattr(m.status, 'value', m.status)
 if status not in ('administrator', 'creator'): raise TelegramError('Bot channel admin nahi hai.')
 if status == 'administrator' and not getattr(m,'can_post_messages',False): raise TelegramError('Bot ke paas Post Messages permission nahi hai.')
async def _send_photo_batch_status(context, uid, chat_id):
 # Telegram delivers each item in an album as a separate update. Wait briefly,
 # then send one status message for the whole burst instead of one per photo.
 try:
  await asyncio.sleep(1.0)
  f = FLOW.get(uid)
  if not f or f.get('step') != 'photos':
   return
  count = len(f.get('photos', []))
  if count >= 10:
   text = '✅ Album/photos add ho gayi. Total: 10 / 10 — ab Done dabao.'
  else:
   text = f'✅ Photos add ho gayi. Total: {count} / 10. Aur photos bhejo ya Done dabao.'
  await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=photo_buttons())
 except Exception:
  log.exception('Could not send batched photo status for user %s', uid)
 finally:
  current = asyncio.current_task()
  if PHOTO_BATCH_TASKS.get(uid) is current:
   PHOTO_BATCH_TASKS.pop(uid, None)

async def handle_photo(update:Update,context:ContextTypes.DEFAULT_TYPE):
 uid=update.effective_user.id; msg=update.effective_message; f=FLOW.get(uid)
 if not f or f.get('step')!='photos':
  await msg.reply_text('Naya post banane ke liye /start → Create Gaming Post dabao.')
  return
 pid=msg.photo[-1].file_id
 if pid not in f['photos'] and len(f['photos'])<10:
  f['photos'].append(pid)
 if len(f['photos']) == 1 and (msg.caption or '').strip() and not f.get('caption'):
  f['caption']=with_brand_hashtags((msg.caption or '').strip()[:850])
 # Restart a short debounce timer; album messages arrive as separate updates.
 old_task = PHOTO_BATCH_TASKS.get(uid)
 if old_task and not old_task.done():
  old_task.cancel()
 PHOTO_BATCH_TASKS[uid] = asyncio.create_task(_send_photo_batch_status(context, uid, msg.chat_id))
async def handle_text(update:Update,context:ContextTypes.DEFAULT_TYPE):
 uid=update.effective_user.id; msg=update.effective_message; txt=(msg.text or '').strip(); f=FLOW.get(uid)
 if not f: await msg.reply_text('Menu ke liye /start dabao.',reply_markup=menu()); return
 if f.get('step')=='own_caption':
  if len(txt)>900: await msg.reply_text('Caption 900 characters se chhota rakho.'); return
  f['caption']=with_brand_hashtags(txt); f['step']='preview'; await msg.reply_text('✅ Caption save ho gaya. Preview neeche hai.')
  await send_preview(context,uid,f)
  await msg.reply_text('👆 Preview ke neeche se next action choose karo:',reply_markup=post_buttons()); return
 if f.get('step')=='connect':
  try:
   target_text = txt.strip()
   if target_text.startswith('https://t.me/'):
    target_text = '@' + target_text.rstrip('/').split('/')[-1]
   target = int(target_text) if target_text.lstrip('-').isdigit() else target_text
   chat=await context.bot.get_chat(target)
   if chat.type != 'channel': raise TelegramError('Ye ID/username Telegram channel ka nahi hai.')
   await verify_channel(context,chat.id); set_user_channel(uid,str(chat.id)); FLOW.pop(uid,None)
   await msg.reply_text(f'✅ Channel connected: {chat.title or chat.username or chat.id}',reply_markup=menu())
  except Exception as e:
   log.exception('Channel connect failed for user %s input %s', uid, txt)
   await msg.reply_text('❌ Connect nahi hua. Check: username public/sahi ho, bot isi channel ka admin ho aur Post Messages permission ho. Private channel mein numeric -100... ID use karo.\nError: '+str(e)[:250],reply_markup=back())
  return
 await msg.reply_text('Current step par diye gaye buttons use karo. Cancel ke liye /cancel bhejo.')
async def my_chat_member(update:Update,context:ContextTypes.DEFAULT_TYPE):
 cm=update.my_chat_member; chat=cm.chat; new=cm.new_chat_member
 if chat.type!='channel': return
 if getattr(new.status, 'value', new.status) in ('administrator', 'creator'):
  # Connect the channel to the Telegram user who added/promoted the bot.
  actor=update.my_chat_member.from_user
  try:
   await verify_channel(context,chat.id); get_user(actor.id,actor.username or '',actor.full_name or '')
   set_user_channel(actor.id,str(chat.id))
   await context.bot.send_message(actor.id,f'✅ Channel auto-detected and connected: {chat.title or chat.id}\nID: {chat.id}')
  except Exception: log.exception('Could not auto-connect channel %s',chat.id)
async def connect_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
 uid=update.effective_user.id
 get_user(uid, update.effective_user.username or '', update.effective_user.full_name or '')
 if not context.args:
  FLOW[uid]={'step':'connect'}
  await update.effective_message.reply_text('Channel ka @username ya numeric ID bhejo. Bot channel admin aur Post Messages permission ke saath hona chahiye.', reply_markup=back())
  return
 target=context.args[0].strip()
 try:
  chat=await context.bot.get_chat(int(target) if target.lstrip('-').isdigit() else target)
  if chat.type != 'channel':
   await update.effective_message.reply_text('❌ Ye channel nahi lag raha. Channel ka @username ya numeric ID bhejo.')
   return
  await verify_channel(context, chat.id)
  set_user_channel(uid, str(chat.id)); FLOW.pop(uid, None)
  await update.effective_message.reply_text(f'✅ Channel connected: {chat.title or chat.username or chat.id}\nID: {chat.id}', reply_markup=menu())
 except TelegramError as e:
  log.exception('Channel connect failed for user %s target %s', uid, target)
  await update.effective_message.reply_text('❌ Channel connect nahi hua. Check karo: username public/sahi ho, bot isi channel ka admin ho, aur Post Messages permission ho. Agar private channel hai to numeric -100... ID use karo.\nError: '+str(e)[:250], reply_markup=back())

async def cancel(update:Update,context:ContextTypes.DEFAULT_TYPE):
 FLOW.pop(update.effective_user.id,None); await update.effective_message.reply_text('Cancelled.',reply_markup=menu())
async def text_router(update,context):
 await handle_text(update,context)
async def photo_router(update,context):
 await handle_photo(update,context)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
 log.exception('Unhandled bot error', exc_info=context.error)
 try:
  if isinstance(update, Update) and update.effective_message:
   await update.effective_message.reply_text('⚠️ Bot ke andar error aaya. Admin ko Logs check karne honge; please wahi action dobara try karo.')
 except Exception:
  log.exception('Could not send error notice')

async def post_init(app): init_db(); log.info('%s started',BOT_NAME)
def main():
 if not TOKEN: raise SystemExit('Set BOT_TOKEN in .env before running.')
 app=Application.builder().token(TOKEN).post_init(post_init).build()
 app.add_handler(CommandHandler('start',start)); app.add_handler(CommandHandler('connect',connect_command)); app.add_handler(CommandHandler('cancel',cancel))
 app.add_handler(CallbackQueryHandler(callback)); app.add_handler(ChatMemberHandler(my_chat_member,ChatMemberHandler.MY_CHAT_MEMBER))
 app.add_handler(MessageHandler(filters.PHOTO,photo_router)); app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_router)); app.add_error_handler(error_handler)
 app.run_polling(allowed_updates=Update.ALL_TYPES)
if __name__=='__main__': main()

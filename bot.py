import os, logging, random
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
ALBUMS = {}
ALBUM_TASKS = {}

CAPTIONS = {
 '🔥 Clutch & Highlights': [
  '🔥 CLUTCH MODE: ON! 🎯\nLast zone, full pressure, clean finish.\n\n#BGMI #WalterBlackMobile #Gaming #Clutch',
  '⚡ One squad. One chance. TOTAL DOMINATION. 🏆\n\n#BGMI #WalterBlack #GamingHighlights #Clutch',
  '🎯 Aim locked. Focus max. Highlight secured. 🔥\n\n#WalterBlackMobile #BGMI #GamerLife'],
 '👑 Royal / Pro Player': [
  '👑 ROYAL GAMEPLAY — BUILT DIFFERENT.\nSkill speaks louder than words. ⚡\n\n#BGMI #WalterBlackMobile #ProPlayer',
  '🏆 No luck, just game sense. Welcome to the lobby! 👑\n\n#BGMI #WalterBlack #GamingCommunity'],
 '💀 Intense Battle': [
  '💀 Every second counts. Every move matters.\nTHE BATTLE IS ON! 🔥\n\n#BGMI #WalterBlackMobile #BattleRoyale',
  '⚔️ Pressure rising. Enemies closing in. We do not back down.\n\n#WalterBlack #BGMI #IntenseGameplay'],
 '🌑 Dark Gaming': [
  '🌑 SILENT MOVES. DEADLY FINISH. 🖤\nThe shadows belong to the skilled.\n\n#BGMI #WalterBlackMobile #DarkGaming',
  '🖤 No noise. No fear. Just precision. 🎯\n\n#Gaming #BGMI #WalterBlack'],
 '😂 Funny Moments': [
  '😂 Plan: perfect. Execution: questionable. Result: CONTENT! 🤣\n\n#BGMI #WalterBlackMobile #FunnyGaming',
  '🤣 Bro thought it was an easy lobby… surprise! 💥\n\n#WalterBlack #BGMI #GamingMemes'],
 '🚀 Trending Gaming': [
  '🚀 NEW HIGHLIGHT DROP! 🔥 Rate this play from 1–10 👇\n\n#BGMI #WalterBlackMobile #GamingReels #ViralGaming',
  '🔥 WATCH TILL THE END! 🎯 This moment hits different.\n\n#BGMI #WalterBlack #GamingHighlights #Gamer'],
}

def menu():
 return InlineKeyboardMarkup([[InlineKeyboardButton('🎮 Create Gaming Post', callback_data='new')], [InlineKeyboardButton('📡 Connected Channel', callback_data='channel'), InlineKeyboardButton('❓ Help', callback_data='help')]])
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
   await send_preview(context,uid,f)
   await q.edit_message_text('✅ Photo ke saath diya gaya caption use kar liya. Ye raha preview:',reply_markup=post_buttons())
  else:
   f['step']='caption_choice'; await q.edit_message_text('📝 Caption kaise banana hai?',reply_markup=caption_buttons())
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
  f['caption']=random.choice(CAPTIONS.get(data[6:],CAPTIONS['🚀 Trending Gaming']))
  f['step']='preview'; await send_preview(context,uid,f); await q.edit_message_text('👆 Ye raha aapka post preview. Kya karna hai?',reply_markup=post_buttons()); return
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
  user=get_user(uid); await q.edit_message_text('📡 CHANNEL STATUS\n\n'+('Connected channel ID: '+str(user['channel']) if user.get('channel') else 'Abhi channel connect nahi hai.')+'\n\nBot ko channel mein admin banao aur Post Messages permission do. Auto-detection na ho to public channel ke liye /connect @channelusername use karo.',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔗 Connect by username/ID',callback_data='connect')],[InlineKeyboardButton('🏠 Main Menu',callback_data='home')]])); return
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
 if m.status not in (ChatMemberStatus.ADMINISTRATOR,ChatMemberStatus.CREATOR): raise TelegramError('Bot channel admin nahi hai.')
 if m.status==ChatMemberStatus.ADMINISTRATOR and not getattr(m,'can_post_messages',False): raise TelegramError('Bot ke paas Post Messages permission nahi hai.')
async def handle_photo(update:Update,context:ContextTypes.DEFAULT_TYPE):
 uid=update.effective_user.id; msg=update.effective_message; f=FLOW.get(uid)
 if not f or f.get('step')!='photos': await msg.reply_text('Naya post banane ke liye /start → Create Gaming Post dabao.'); return
 pid=msg.photo[-1].file_id
 if pid not in f['photos'] and len(f['photos'])<10: f['photos'].append(pid)
 if len(f['photos']) == 1 and (msg.caption or '').strip() and not f.get('caption'):
  f['caption']=(msg.caption or '').strip()[:900]
 if len(f['photos'])>=10:
  await msg.reply_text('✅ Photo add ho gayi. Total: 10 / 10 — ab Done dabao.',reply_markup=photo_buttons())
 else:
  await msg.reply_text(f'✅ Photo add ho gayi. Total: {len(f["photos"])} / 10. Aur photos bhej sakte ho ya Done dabao.',reply_markup=photo_buttons())
async def handle_text(update:Update,context:ContextTypes.DEFAULT_TYPE):
 uid=update.effective_user.id; msg=update.effective_message; txt=(msg.text or '').strip(); f=FLOW.get(uid)
 if not f: await msg.reply_text('Menu ke liye /start dabao.',reply_markup=menu()); return
 if f.get('step')=='own_caption':
  if len(txt)>900: await msg.reply_text('Caption 900 characters se chhota rakho.'); return
  f['caption']=txt; f['step']='preview'; await send_preview(context,uid,f); await msg.reply_text('👆 Post preview ready hai. Choose:',reply_markup=post_buttons()); return
 if f.get('step')=='connect':
  try:
   chat=await context.bot.get_chat(txt); await verify_channel(context,chat.id); set_user_channel(uid,str(chat.id)); FLOW.pop(uid,None)
   await msg.reply_text(f'✅ Channel connected: {chat.title or chat.username or chat.id}',reply_markup=menu())
  except TelegramError as e: await msg.reply_text('❌ Connect nahi hua. Bot admin, channel ID aur Post Messages permission check karo.\n'+str(e)[:220],reply_markup=back())
  return
 await msg.reply_text('Current step par diye gaye buttons use karo. Cancel ke liye /cancel bhejo.')
async def my_chat_member(update:Update,context:ContextTypes.DEFAULT_TYPE):
 cm=update.my_chat_member; chat=cm.chat; new=cm.new_chat_member
 if chat.type!='channel': return
 if new.status in (ChatMemberStatus.ADMINISTRATOR,ChatMemberStatus.CREATOR):
  # Connect the channel to the Telegram user who added/promoted the bot.
  actor=update.my_chat_member.from_user
  try:
   await verify_channel(context,chat.id); get_user(actor.id,actor.username or '',actor.full_name or '')
   set_user_channel(actor.id,str(chat.id))
   await context.bot.send_message(actor.id,f'✅ Channel auto-detected and connected: {chat.title or chat.id}\nID: {chat.id}')
  except Exception: log.exception('Could not auto-connect channel %s',chat.id)
async def cancel(update:Update,context:ContextTypes.DEFAULT_TYPE):
 FLOW.pop(update.effective_user.id,None); await update.effective_message.reply_text('Cancelled.',reply_markup=menu())
async def text_router(update,context):
 await handle_text(update,context)
async def photo_router(update,context):
 await handle_photo(update,context)
async def post_init(app): init_db(); log.info('%s started',BOT_NAME)
def main():
 if not TOKEN: raise SystemExit('Set BOT_TOKEN in .env before running.')
 app=Application.builder().token(TOKEN).post_init(post_init).build()
 app.add_handler(CommandHandler('start',start)); app.add_handler(CommandHandler('cancel',cancel))
 app.add_handler(CallbackQueryHandler(callback)); app.add_handler(ChatMemberHandler(my_chat_member,ChatMemberHandler.MY_CHAT_MEMBER))
 app.add_handler(MessageHandler(filters.PHOTO,photo_router)); app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_router))
 app.run_polling(allowed_updates=Update.ALL_TYPES)
if __name__=='__main__': main()

# Message handlers for Telegram bot
import pytz
from datetime import timedelta, datetime
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from firebase_admin import firestore

def setup_message_handlers(bot):
    """Register all message handlers with the bot"""
    
    @bot.message_handler(commands=['start', 'help'])
    def welcome(message):
        from main import db
        from meeting import is_user_registered
        
        if is_user_registered(message.from_user.id):
            bot.reply_to(message, "MeetFlow ready!\n\nCreate meeting: `tomorrow 10am standup -room A1`\n\nCommands: /today  /thisweek  /mymeetings", parse_mode="Markdown")
        else:
            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            markup.add(types.KeyboardButton("Share my phone number", request_contact=True))
            bot.send_message(message.chat.id, "Hi! To get started, please share your phone number (just once).", reply_markup=markup)

    @bot.message_handler(content_types=['contact'])
    def handle_contact(message):
        from main import db
        
        if message.contact:
            user_id = str(message.from_user.id)
            db.collection('users').document(user_id).set({
                'phone': message.contact.phone_number,
                'username': message.from_user.username or "",
                'first_name': message.from_user.first_name,
                'created_at': firestore.SERVER_TIMESTAMP
            }, merge=True)
            bot.send_message(message.chat.id, "Thank you! You're all set.\nTry: `friday 3pm client call`", reply_markup=types.ReplyKeyboardRemove())

    @bot.message_handler(commands=['today', 'thisweek', 'mymeetings'])
    def list_meetings(message):
        from main import db, TIMEZONE
        from meeting import is_user_registered, get_user_meetings, build_meeting_markup
        
        if not is_user_registered(message.from_user.id): 
            return welcome(message)
        user_id = str(message.from_user.id)
        cmd = message.text.split()[0][1:].lower()
        now = datetime.now(pytz.utc)
        start = end = None
        title = "Your Meetings"

        if cmd == 'today':
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
            title = "Today's Meetings"
        elif cmd == 'thisweek':
            start = now
            end = now + timedelta(days=7)
            title = "This Week"

        meetings = get_user_meetings(user_id, start, end)
        if not meetings:
            bot.reply_to(message, f"{title}: none.")
            return

        text = f"**{title}** ({len(meetings)})\n\n"
        markup = InlineKeyboardMarkup(row_width=1)
        for m in sorted(meetings, key=lambda x: x['date_time']):
            short = m['meeting_id'][:8]
            dt = m['date_time'].astimezone(TIMEZONE)
            btn_text = f"{'[OK]' if m.get('status')=='scheduled' else '[CANCELLED]'} {dt.strftime('%H:%M')} - {m['title'][:30]}"
            markup.add(InlineKeyboardButton(btn_text, callback_data=f"details:{short}"))
        bot.reply_to(message, text, parse_mode="Markdown", reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: True)
    def callback_handler(call):
        from main import db, TIMEZONE
        from meeting import (is_user_registered, find_meeting_by_short_id, get_username,
                            get_rsvp_details, build_meeting_details_text, build_meeting_markup)
        
        user_id_str = str(call.from_user.id)
        if not is_user_registered(call.from_user.id):
            return bot.answer_callback_query(call.id, "Start bot first", show_alert=True)

        action, short_id = (call.data.split(":", 1) if ":" in call.data else ("", ""))

        meeting = find_meeting_by_short_id(user_id_str, short_id)
        if not meeting:
            return bot.answer_callback_query(call.id, "Meeting not found", show_alert=True)

        mid = meeting['meeting_id']
        creator_id = meeting['creator_id']

        # RSVP actions
        if action.startswith("rsvp_"):
            status = {"rsvp_yes":"yes", "rsvp_maybe":"maybe", "rsvp_no":"no"}[action]
            db.collection('meetings').document(mid).update({f'rsvp.{user_id_str}': status})

            # Notify creator
            if creator_id != user_id_str:
                uname = get_username(user_id_str) or "Someone"
                status_text = {"yes":"Going [OK]", "maybe":"Maybe [?]", "no":"Not going [X]"}[status]
                bot.send_message(creator_id, f"RSVP > {meeting['title']}\n{uname} is {status_text}")

            # Refresh view
            rsvp_info = get_rsvp_details(meeting)
            text = build_meeting_details_text(meeting, rsvp_info, user_id_str)
            markup = build_meeting_markup(short_id, rsvp_info['total'] > 0)
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text=text, parse_mode="Markdown", reply_markup=markup)
            bot.answer_callback_query(call.id, "[OK] RSVP updated!")

        # Details / Refresh
        elif action in ["details", "refresh"]:
            rsvp_info = get_rsvp_details(meeting)
            text = build_meeting_details_text(meeting, rsvp_info, user_id_str)
            markup = build_meeting_markup(short_id, rsvp_info['total'] > 0)
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text=text, parse_mode="Markdown", reply_markup=markup)
            bot.answer_callback_query(call.id)

        # Cancel
        elif action == "cancel":
            db.collection('meetings').document(mid).update({'status': 'canceled'})
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text=f"[CANCELLED]:\n**{meeting['title']}**", parse_mode="Markdown")
            bot.answer_callback_query(call.id, "Canceled")

        # Reschedule
        elif action == "reschedule":
            bot.answer_callback_query(call.id, "Use /reschedule code +1h", show_alert=True)

    @bot.message_handler(func=lambda m: True)
    def natural_creation(message):
        from main import db, TIMEZONE
        from meeting import is_user_registered, improved_parse_meeting_request, create_meeting
        
        if not is_user_registered(message.from_user.id): 
            return welcome(message)
        text = message.text.strip()
        if message.entities:
            for e in message.entities:
                if e.type == 'mention' and f"@{bot.get_me().username}" in text:
                    text = text[e.length:].strip()

        parsed = improved_parse_meeting_request(text)
        if parsed:
            mid, meeting = create_meeting(parsed, str(message.from_user.id))
            dt_str = meeting['date_time'].astimezone(TIMEZONE).strftime("%a %d %b %Y %H:%M")
            reply = f"Created!\n**{meeting['title']}**\n[TIME] {dt_str}\nID: `{mid[:8]}...`"
            if meeting['participants']: 
                reply += f"\n@{' @'.join(meeting['participants'])}"
            bot.reply_to(message, reply, parse_mode="Markdown")
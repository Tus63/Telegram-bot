# Import ONLY non-circular dependencies at module level
from firebase_admin import firestore
from datetime import timedelta
import uuid
import pytz
import re
import dateparser
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

def improved_parse_meeting_request(text):
    parsed_dates = dateparser.search_dates(text, settings={'PREFER_DATES_FROM': 'future', 'RETURN_AS_TIMEZONE_AWARE': True})
    if not parsed_dates: return None
    dt_match, dt = parsed_dates[0]
    title_part = text.replace(dt_match, '', 1).strip()
    title_part = re.sub(r'^(schedule|meet|meeting|at|on|for)\s+', '', title_part, flags=re.I)
    title_part = re.sub(r'\s+', ' ', title_part).strip() or "Team Meeting"

    participants = [p.lstrip('@') for p in re.findall(r'@[\w]+', text)]
    flags = {}
    for m in re.finditer(r'-(\w+)(?:\s+([^\s]+(?:\s+[^\s]+)*))?', text):
        flags[m.group(1).lower()] = (m.group(2) or '').strip()

    online_link = "https://meet.google.com/new" if any(x in text.lower() for x in ['meet', 'zoom', 'teams']) else None

    return {
        'title': title_part,
        'date_time': dt,
        'participants': participants,
        'location': flags.get('room') or flags.get('location'),
        'online_link': online_link,
        'calendar_name': flags.get('calendar', 'Personal')
    }

def create_meeting(data, creator_id):
    from main import db
    meeting_id = str(uuid.uuid4())
    meeting = {
        'meeting_id': meeting_id,
        'title': data['title'],
        'date_time': data['date_time'].astimezone(pytz.utc),
        'creator_id': creator_id,
        'calendar_name': data['calendar_name'],
        'participants': data['participants'],
        'location': data.get('location'),
        'online_link': data.get('online_link'),
        'status': 'scheduled',
        'rsvp': {},  # ← new
        'created_at': firestore.SERVER_TIMESTAMP
    }
    db.collection('meetings').document(meeting_id).set(meeting)

    # Auto RSVP "yes" for mentioned users who exist
    if data['participants']:
        auto_set_rsvp_for_mentioned(meeting_id, data['participants'])

    # Reminder
    remind_at = data['date_time'] - timedelta(minutes=30)
    db.collection('reminders').add({
        'meeting_id': meeting_id,
        'user_id': creator_id,
        'remind_at': remind_at.astimezone(pytz.utc),
        'sent': False,
        'meeting_title': data['title']
    })
    return meeting_id, meeting

def auto_set_rsvp_for_mentioned(meeting_id, participants):
    from main import db
    from firebase_admin import firestore
    for username in participants:
        users = db.collection('users').where(filter=firestore.FieldFilter('username', '==', username)).limit(1).stream()
        for user_doc in users:
            db.collection('meetings').document(meeting_id).update({
                f'rsvp.{user_doc.id}': 'yes'
            })

def get_username(user_id):
    from main import db
    doc = db.collection('users').document(str(user_id)).get()
    if doc.exists:
        uname = doc.to_dict().get('username')
        if uname: return f"@{uname}"
    return None

def get_rsvp_details(meeting):
    rsvp = meeting.get('rsvp', {})
    yes_names = [get_username(uid) for uid, st in rsvp.items() if st == 'yes' and get_username(uid)]
    maybe_names = [get_username(uid) for uid, st in rsvp.items() if st == 'maybe' and get_username(uid)]
    yes_count = sum(1 for v in rsvp.values() if v == 'yes')
    maybe_count = sum(1 for v in rsvp.values() if v == 'maybe')
    no_count = sum(1 for v in rsvp.values() if v == 'no')
    return {
        'yes_count': yes_count, 'maybe_count': maybe_count, 'no_count': no_count,
        'yes_names': yes_names, 'maybe_names': maybe_names,
        'total': len(rsvp)
    }

def find_meeting_by_short_id(user_id, short_id):
    from main import db
    from firebase_admin import firestore
    meetings = db.collection('meetings').where(filter=firestore.FieldFilter('creator_id', '==', user_id)).stream()
    for m in meetings:
        doc = m.to_dict()
        if doc['meeting_id'].startswith(short_id):
            return doc
    return None

def get_user_meetings(user_id, start=None, end=None):
    from main import db
    from firebase_admin import firestore
    query = db.collection('meetings').where(filter=firestore.FieldFilter('creator_id', '==', user_id))
    if start: query = query.where(filter=firestore.FieldFilter('date_time', '>=', start))
    if end: query = query.where(filter=firestore.FieldFilter('date_time', '<=', end))
    return [m.to_dict() for m in query.stream()]

def is_user_registered(user_id):
    from main import db
    doc = db.collection('users').document(str(user_id)).get()
    return doc.exists and doc.to_dict().get('phone') is not None

# Build text & markup (used in callback)
def build_meeting_details_text(meeting, rsvp_info, current_user_id):
    from main import TIMEZONE
    mid = meeting['meeting_id']
    dt_local = meeting['date_time'].astimezone(TIMEZONE)
    dt_str = dt_local.strftime("%a %d %b %Y  %H:%M")
    text = f"**{meeting['title']}**\n🕒 {dt_str}\nID: `{mid[:8]}…`\nStatus: {meeting.get('status','scheduled')}\n"
    if meeting.get('location'): text += f"📍 {meeting['location']}\n"
    if meeting.get('online_link'): text += f"🔗 [Join]({meeting['online_link']})\n\n"

    text += "**RSVP**\n"
    text += f"✅ Going: {rsvp_info['yes_count']}   🤔 Maybe: {rsvp_info['maybe_count']}   ❌ Not: {rsvp_info['no_count']}\n"
    if rsvp_info['yes_names']: text += "Going: " + ", ".join(rsvp_info['yes_names']) + "\n"
    if rsvp_info['maybe_names']: text += "Maybe: " + ", ".join(rsvp_info['maybe_names']) + "\n"

    my_status = meeting.get('rsvp', {}).get(current_user_id, "not responded")
    emoji = {"yes":"✅","maybe":"🤔","no":"❌"}.get(my_status, "❓")
    text += f"\nYour choice: {emoji} {my_status.capitalize()}"
    return text

def build_meeting_markup(short_id, has_rsvp=False):
    markup = InlineKeyboardMarkup(row_width=3)
    markup.row(
        InlineKeyboardButton("✅ Going", callback_data=f"rsvp_yes:{short_id}"),
        InlineKeyboardButton("🤔 Maybe", callback_data=f"rsvp_maybe:{short_id}"),
        InlineKeyboardButton("❌ Not going", callback_data=f"rsvp_no:{short_id}")
    )
    markup.row(
        InlineKeyboardButton("Reschedule", callback_data=f"reschedule:{short_id}"),
        InlineKeyboardButton("Cancel", callback_data=f"cancel:{short_id}")
    )
    if has_rsvp:
        markup.row(InlineKeyboardButton("↻ Refresh", callback_data=f"refresh:{short_id}"))
    return markup
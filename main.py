import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta
import dateparser
import uuid
import pytz
import re
import threading
import time

import telebot
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# Use the exact filename you uploaded
cred = credentials.Certificate("telegram-bot.json")

# Check if Firebase app is already initialized to prevent ValueError
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(cred)

db = firestore.client()

TOKEN = "8016301456:AAH7W0TDpXgS21K6SE0BdzWmv-x4yn_iac0"  # Replace with your token
bot = telebot.TeleBot(TOKEN)

TIMEZONE = pytz.timezone('Asia/Phnom_Penh')  # Adjust if needed

# ===== IMPORT MEETING MODULE (must be after initialization to avoid circular imports) =====
from meeting import (
    improved_parse_meeting_request, create_meeting, get_rsvp_details,
    build_meeting_details_text, build_meeting_markup, find_meeting_by_short_id,
    get_user_meetings, is_user_registered
)

# ===== SETUP MESSAGE HANDLERS =====
from messagehander import setup_message_handlers
setup_message_handlers(bot)

# ===== MEETING COMMAND HANDLERS =====

@bot.message_handler(commands=['schedule'])
def schedule_meeting(message):
    """Handle /schedule command"""
    user_id = message.from_user.id
    
    if not is_user_registered(user_id):
        bot.reply_to(message, "Please register first using /start")
        return
    
    bot.reply_to(message, "Send me meeting details in the format:\n"
                          "schedule meet or meeting title @participant1 @participant2\n"
                          "Example: schedule Team sync @alice @bob")
    bot.register_next_step_handler(message, process_meeting_request)

def process_meeting_request(message):
    """Process user's meeting request"""
    user_id = message.from_user.id
    
    try:
        parsed_data = improved_parse_meeting_request(message.text)
        
        if not parsed_data:
            bot.reply_to(message, "[ERROR] Couldn't parse meeting details. Please try again with a date/time.")
            return
        
        meeting_id, meeting = create_meeting(parsed_data, user_id)
        rsvp_info = get_rsvp_details(meeting)
        short_id = meeting_id[:8]
        
        details_text = build_meeting_details_text(meeting, rsvp_info, user_id)
        markup = build_meeting_markup(short_id, has_rsvp=True)
        
        bot.send_message(message.chat.id, details_text, 
                        parse_mode='Markdown', reply_markup=markup)
    except Exception as e:
        bot.reply_to(message, f"[ERROR] Error creating meeting: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('rsvp_'))
def handle_rsvp(call):
    """Handle RSVP button clicks"""
    try:
        parts = call.data.split(':')
        rsvp_choice = parts[0].split('_')[1]  # 'yes', 'maybe', 'no'
        short_id = parts[1]
        user_id = call.from_user.id
        
        meeting = find_meeting_by_short_id(meeting['creator_id'], short_id)
        if not meeting:
            bot.answer_callback_query(call.id, "[ERROR] Meeting not found")
            return
        
        # Update RSVP in Firestore
        db.collection('meetings').document(meeting['meeting_id']).update({
            f'rsvp.{user_id}': rsvp_choice
        })
        
        rsvp_info = get_rsvp_details(meeting)
        details_text = build_meeting_details_text(meeting, rsvp_info, user_id)
        markup = build_meeting_markup(short_id, has_rsvp=True)
        
        bot.edit_message_text(details_text, call.message.chat.id, 
                             call.message.message_id, 
                             parse_mode='Markdown', reply_markup=markup)
        bot.answer_callback_query(call.id, f"[OK] Your RSVP: {rsvp_choice}")
    except Exception as e:
        bot.answer_callback_query(call.id, f"[ERROR] Error: {str(e)}")

# ===== START BACKGROUND SERVICES =====
from remainder import start_reminder_scheduler

# Start the reminder scheduler in background (only in main execution)

# ===== START BOT POLLING =====
if __name__ == '__main__':
    import sys
    
    # Initialize services only when script runs directly
    print("[OK] Firebase connected successfully!")
    print("[OK] MeetFlow bot initialized!")
    start_reminder_scheduler()
    print("[OK] MeetFlow is LIVE! Your bot is ready in Phnom Penh time")
    print("[OK] Starting bot polling in 2 seconds...")
    time.sleep(2)
    
    try:
        print("[OK] Bot is LIVE! Waiting for messages...")
        bot.infinity_polling(timeout=10, long_polling_timeout=5, skip_pending=True)
        
    except KeyboardInterrupt:
        print("\n[OK] Bot stopped by user (Ctrl+C)")
        sys.exit(0)
        
    except Exception as e:
        error_msg = str(e)
        
        # Handle 409 Conflict (another bot instance running)
        if "409" in error_msg or "getUpdates" in error_msg:
            print("\n" + "="*70)
            print("[FATAL ERROR] Telegram 409 Conflict!")
            print("="*70)
            print("\nAnother bot instance is STILL running with this token.")
            print("\nFIX THIS NOW:")
            print("  1. CLOSE ALL terminals and VS Code completely")
            print("  2. Open Windows Task Manager (Ctrl+Shift+Esc)")
            print("  3. Find 'python.exe' → Select it → Click 'End Task'")
            print("  4. WAIT 60 SECONDS (required by Telegram)")
            print("  5. Reopen PowerShell and run: python main.py")
            print("\nOR use the cleanup script:")
            print("  cd 'd:\\project telegram bot'")
            print("  .\\cleanup.ps1")
            print("="*70)
            sys.exit(1)
        else:
            print(f"\n[ERROR] Unexpected polling error:")
            print(f"  {error_msg[:300]}")
            sys.exit(1)
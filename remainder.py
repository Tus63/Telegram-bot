import threading
import time
import pytz
from datetime import datetime
from firebase_admin import firestore

def start_reminder_scheduler():
    """Start background thread for meeting reminders"""
    from main import db, bot
    
    def scheduler():
        while True:
            try:
                now = datetime.now(pytz.utc)
                reminders = db.collection('reminders')\
                    .where(filter=firestore.FieldFilter('remind_at', '<=', now))\
                    .where(filter=firestore.FieldFilter('sent', '==', False)).stream()

                for r in reminders:
                    data = r.to_dict()
                    try:
                        bot.send_message(data['user_id'],
                            f"[REMINDER] {data['meeting_title']} is starting soon!")
                        r.reference.update({'sent': True})
                    except Exception as e:
                        print(f"Failed to send reminder: {e}")
            except Exception as e:
                print("Scheduler error:", e)
            time.sleep(45)  # Check every 45s

    thread = threading.Thread(target=scheduler, daemon=True)
    thread.start()
    print("[OK] Reminder scheduler started")
# MeetFlow Telegram Bot - Quick Start Guide

## Problem: Error 409 "Conflict: terminated by other getUpdates request"

This error means **two bot instances are trying to poll Telegram simultaneously**. Only ONE bot can run at a time.

## Solution: Quick Cleanup & Restart

### Option 1: Using the Cleanup Script (Recommended)
```powershell
# Open PowerShell in the project directory, then run:
.\cleanup.ps1
```

This will:
1. Kill all Python processes
2. Wait 45 seconds for Telegram to release the connection
3. Verify everything is clean
4. Tell you when it's ready to start

### Option 2: Using the Batch Script (Windows)
```cmd
start_bot.bat
```

This will automatically kill processes, wait, and start the bot in one command.

### Option 3: Manual Cleanup
1. **Close all terminals** running the bot
2. **Close VS Code** completely
3. Open **Windows Task Manager** (Ctrl+Shift+Esc)
4. Find `python.exe` → Right-click → **End Task**
5. Wait **45-60 seconds**
6. Open PowerShell and run:
   ```powershell
   cd "d:\project telegram bot"
   python main.py
   ```

## If Error Persists

1. Make sure **all** `python.exe` processes are killed in Task Manager
2. Close your entire IDE/VS Code
3. Restart your computer (last resort)
4. Wait 2 minutes before trying again

## How to Prevent This

- Don't run the bot in multiple terminals
- Don't run the script multiple times with `import main`
- The bot uses `if __name__ == '__main__':` to prevent re-execution
- Only one `python main.py` process should be running at a time

## Current Bot Features

✅ Meeting scheduling with natural language  
✅ RSVP tracking and notifications  
✅ Automatic reminders 15 minutes before  
✅ User registration & contact storage  
✅ Firebase Firestore integration  
✅ Telegram commands: /start, /help, /today, /thisweek, /mymeetings  

## Bot Commands

- `/start` - Register and get help
- `/help` - Show help message
- `/today` - Show today's meetings
- `/thisweek` - Show meetings this week
- `/mymeetings` - Show all your meetings

## Text-based Meeting Creation

Just send a message like:
```
tomorrow 10am standup -room A1 @alice @bob
friday 3pm client call
next monday 2pm with marketing team
```

The bot will parse the date/time and create the meeting!

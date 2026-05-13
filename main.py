import logging
import os
import asyncio
import subprocess
import random
from pathlib import Path
import re
import json
from datetime import datetime, timedelta, timezone
import base64

try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
except ImportError:
    print("python-telegram-bot is not installed. Installing it now...")
    try:
        subprocess.check_call(["pip3", "install", "python-telegram-bot"])
        print("python-telegram-bot has been successfully installed.")
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
    except Exception as e:
        try:
            subprocess.check_call(["pip", "install", "python-telegram-bot"])
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
            print("python-telegram-bot has been successfully installed using pip3.")
        except Exception as e:
            print("Failed to install python-telegram-bot with pip and pip3:", str(e))
            exit(0)

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

try:
    from telethon import TelegramClient, sync, functions, errors, events, types
    from telethon.tl.functions.channels import LeaveChannelRequest
except ImportError:
    print("telethon is not installed. Installing it now...")
    try:
        subprocess.check_call(["pip3", "install", "telethon"])
        print("telethon has been successfully installed.")
        from telethon import TelegramClient, sync, functions, errors, events, types
    except Exception as e:
        try:
            subprocess.check_call(["pip", "install", "telethon"])
            from telethon import TelegramClient, sync, functions, errors, events, types
            print("telethon has been successfully installed using pip.")
        except Exception as e:
            print("Failed to install telethon with pip and pip:", str(e))
            exit(0)

from telethon.tl.functions.account import UpdateStatusRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest, GetMessagesViewsRequest, SendReactionRequest, GetHistoryRequest, SendVoteRequest, CheckChatInviteRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest
from telethon.tl.functions.account import UpdateProfileRequest, ReportPeerRequest
from telethon.tl.functions.payments import CheckGiftCodeRequest
from telethon.tl.types import MessageActionGiftCode, MessageMediaPoll, InputPeerUser, InputPeerChannel

try:
    import requests
except ImportError:
    print("requests is not installed. Installing it now...")
    try:
        subprocess.check_call(["pip3", "install", "requests"])
        print("requests has been successfully installed.")
        import requests
    except Exception as e:
        try:
            subprocess.check_call(["pip", "install", "requests"])
            import requests
            print("requests has been successfully installed using pip.")
        except Exception as e:
            print("Failed to install requests with pip and pip:", str(e))
            exit(0)

try:
    import aiohttp
except ImportError:
    print("aiohttp is not installed. Installing it now...")
    try:
        subprocess.check_call(["pip3", "install", "aiohttp"])
        print("aiohttp has been successfully installed.")
        import aiohttp
    except Exception as e:
        try:
            subprocess.check_call(["pip", "install", "aiohttp"])
            import aiohttp
            print("aiohttp has been successfully installed using pip.")
        except Exception as e:
            print("Failed to install aiohttp with pip and pip:", str(e))
            exit(0)

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
except ImportError:
    print("cryptography is not installed. Installing it now...")
    try:
        subprocess.check_call(["pip3", "install", "cryptography"])
        print("cryptography has been successfully installed.")
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    except Exception as e:
        try:
            subprocess.check_call(["pip", "install", "cryptography"])
            from cryptography.fernet import Fernet
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            print("cryptography has been successfully installed using pip.")
        except Exception as e:
            print("Failed to install cryptography with pip and pip:", str(e))
            exit(0)

from concurrent.futures import ThreadPoolExecutor
import atexit

# زيادة timeout للاتصالات
import socket
socket.setdefaulttimeout(30)

bot_token = "8760621533:AAHTfU9zLoNeE1nTJO2TedToMwgbUFyWaeY"
sudo_id = "8649781533"

API_ID = '34398289'
API_HASH = 'b3571778edd08c6483a3c597c65b544d'
running_processes = {}
clients = {}
what_need_to_do_echo = {}
points_data = {}

# قنوات الاشتراك الإجباري (معطلة حالياً)
REQUIRED_CHANNELS = []
FORCE_SUBSCRIBE_ENABLED = False  # تم تعطيل الاشتراك الإجباري

# تحسينات السرعة - تخزين مؤقت للجلسات
_session_cache = {}
thread_pool = ThreadPoolExecutor(max_workers=4)

# ============ نظام الاتصال المتقدم ============
class ConnectionPool:
    """إدارة مركزية للاتصالات تمنع تسريب الذاكرة"""
    _clients = {}
    _locks = {}
    
    @classmethod
    async def get_client(cls, phone, user_id):
        key = f"{phone}-{user_id}"
        if key not in cls._locks:
            cls._locks[key] = asyncio.Lock()
        
        async with cls._locks[key]:
            if key not in cls._clients or not cls._clients[key].is_connected():
                client = TelegramClient(
                    f"echo_ac/{user_id}/{phone}", 
                    API_ID, API_HASH,
                    device_model="iPhone 15 Pro Max",
                    system_version="iOS 17.4",
                    app_version="10.9.1",
                    timeout=30,
                    connection_retries=3
                )
                await client.connect()
                cls._clients[key] = client
            return cls._clients[key]
    
    @classmethod
    async def cleanup(cls):
        """تنظيف جميع الاتصالات عند إغلاق البوت"""
        for key, client in cls._clients.items():
            try:
                if client.is_connected():
                    await client.disconnect()
            except:
                pass
        cls._clients.clear()

# ============ API متقدم مع aiohttp ============
class KekoAPI:
    """تعامل موحد وسريع مع API كيكو"""
    def __init__(self):
        self.session = None
        self.base_url = "https://bot.keko.dev/api/"
        
    async def get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                connector=aiohttp.TCPConnector(limit=100, limit_per_host=20)
            )
        return self.session
    
    async def request(self, params):
        session = await self.get_session()
        try:
            async with session.get(self.base_url, params=params) as response:
                return await response.json()
        except:
            return requests.get(self.base_url, params=params, timeout=10).json()
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

keko_api = KekoAPI()

# ============ نظام الإشعارات المتقدم ============
class TelegramNotifier:
    """مدير مركزي لإرسال رسائل التلجرام بسرعة"""
    def __init__(self, token):
        self.token = token
        self.session = None
        self.queue = asyncio.Queue()
        self.running = False
        
    async def start(self):
        self.session = aiohttp.ClientSession()
        self.running = True
        asyncio.create_task(self._worker())
        
    async def _worker(self):
        batch = []
        last_send = datetime.now()
        
        while self.running:
            try:
                try:
                    msg = await asyncio.wait_for(self.queue.get(), timeout=0.1)
                    batch.append(msg)
                except asyncio.TimeoutError:
                    pass
                
                if len(batch) >= 10 or (batch and (datetime.now() - last_send).seconds >= 1):
                    await self._send_batch(batch)
                    batch = []
                    last_send = datetime.now()
            except:
                pass
    
    async def _send_batch(self, messages):
        tasks = []
        for chat_id, text in messages:
            tasks.append(self._send_one(chat_id, text))
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _send_one(self, chat_id, text):
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        try:
            async with self.session.post(url, json={"chat_id": chat_id, "text": text[:4000]}) as resp:
                return await resp.json()
        except:
            return requests.post(url, json={"chat_id": chat_id, "text": text[:4000]}).json()
    
    async def send(self, chat_id, text):
        await self.queue.put((chat_id, text))
    
    async def stop(self):
        self.running = False
        if self.session:
            await self.session.close()

notifier = TelegramNotifier(bot_token)

async def send_telegram_message(chat_id, text):
    await notifier.send(chat_id, text)

import base64
import json
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend


# ============ نظام التخزين الآمن ============
class SecureStorage:
    """تخزين آمن للبيانات الحساسة"""
    _key = None

    @classmethod
    def init_key(cls, password):
        salt = b'echo_bot_salt_2024'

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )

        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        cls._key = Fernet(key)

    @classmethod
    def encrypt(cls, data):
        if isinstance(data, dict):
            data = json.dumps(data)
        return cls._key.encrypt(data.encode()).decode()

    @classmethod
    def decrypt(cls, encrypted_data):
        decrypted = cls._key.decrypt(encrypted_data.encode())
        return json.loads(decrypted)

# ============ نظام التحليلات والمراقبة ============
class BotAnalytics:
    """نظام تحليلات بسيط للبوت"""
    stats = {
        'messages_sent': 0,
        'tasks_completed': 0,
        'errors': 0,
        'active_users': set(),
        'start_time': datetime.now(),
        'broadcasts_sent': 0,
        'broadcast_recipients': 0,
        'links_processed': 0
    }
    
    @classmethod
    def track_event(cls, event_type, user_id=None, count=1):
        if event_type == 'message':
            cls.stats['messages_sent'] += count
        elif event_type == 'task':
            cls.stats['tasks_completed'] += count
        elif event_type == 'error':
            cls.stats['errors'] += count
        elif event_type == 'user_active' and user_id:
            cls.stats['active_users'].add(user_id)
        elif event_type == 'broadcast':
            cls.stats['broadcasts_sent'] += 1
            cls.stats['broadcast_recipients'] += count
        elif event_type == 'link':
            cls.stats['links_processed'] += count
    
    @classmethod
    def get_stats(cls):
        uptime = datetime.now() - cls.stats['start_time']
        days = uptime.days
        hours = uptime.seconds // 3600
        minutes = (uptime.seconds % 3600) // 60
        
        return f"""
📊 **إحصائيات البوت**

⏱️ **وقت التشغيل:** {days} يوم, {hours} ساعة, {minutes} دقيقة
👥 **المستخدمين النشطين:** {len(cls.stats['active_users'])}
📨 **الرسائل المرسلة:** {cls.stats['messages_sent']}
✅ **المهام المكتملة:** {cls.stats['tasks_completed']}
🔗 **الروابط المعالجة:** {cls.stats['links_processed']}
📢 **الإذاعات المرسلة:** {cls.stats['broadcasts_sent']}
👤 **مستلمي الإذاعة:** {cls.stats['broadcast_recipients']}
❌ **الأخطاء:** {cls.stats['errors']}
        """.strip()

# ============ نظام إدارة الجلسات ============
class SessionManager:
    """إدارة ذكية لملفات الجلسات مع كاش"""
    _cache = {}
    _last_access = {}
    
    @classmethod
    def get_sessions(cls, user_id):
        user_id = str(user_id)
        now = datetime.now()
        
        if user_id in cls._cache and (now - cls._last_access.get(user_id, now)).seconds < 30:
            return cls._cache[user_id]
        
        path = Path(f"echo_ac/{user_id}")
        if path.is_dir():
            sessions = [f.stem for f in path.glob('*.session')]
            cls._cache[user_id] = sessions
            cls._last_access[user_id] = now
            return sessions
        return []
    
    @classmethod
    def invalidate(cls, user_id):
        cls._cache.pop(str(user_id), None)
        cls._last_access.pop(str(user_id), None)

def get_active_accounts(user_id):
    """الحصول على الحسابات المسجلة"""
    return SessionManager.get_sessions(user_id)

def get_running_accounts(user_id):
    """الحصول على الحسابات قيد التشغيل"""
    user_id = str(user_id)
    if user_id in running_processes:
        return [k for k in running_processes[user_id].keys() if not k.startswith('custom_')]
    return []

# ============ نظام معالجة الروابط المتقدم ============
class LinkProcessor:
    """معالجة ذكية للروابط - بوت أو قناة"""
    
    @staticmethod
    async def detect_link_type(link):
        """تحديد نوع الرابط"""
        link = link.strip()
        
        # التحقق من رابط بوت
        if 't.me/' in link and ('?start=' in link or link.endswith('bot') or 'bot' in link):
            return 'bot'
        
        # التحقق من رابط قناة/مجموعة
        if 't.me/' in link or 'telegram.me/' in link:
            return 'channel'
        
        return 'unknown'
    
    @staticmethod
    async def extract_bot_info(link):
        """استخراج معلومات البوت من الرابط"""
        match = re.search(r"t\.me/([^?/]+)(?:\?start=(.+))?", link)
        if match:
            bot_username = match.group(1)
            start_payload = match.group(2)
            return bot_username, start_payload
        return None, None
    
    @staticmethod
    async def extract_channel_info(link):
        """استخراج معلومات القناة من الرابط"""
        try:
            if "t.me/+" in link or "telegram.me/+" in link:
                invite_hash = link.split('+')[1].strip().split('/')[0]
                return {'type': 'invite', 'hash': invite_hash}
            elif "joinchat/" in link:
                invite_hash = link.split('joinchat/')[1].strip().split('/')[0]
                return {'type': 'invite', 'hash': invite_hash}
            else:
                username = link.split('/')[-1]
                return {'type': 'username', 'username': username}
        except:
            return None
    
    @staticmethod
    async def process_bot_link(user_id, link, accounts=None):
        """معالجة رابط بوت - إرسال start والتفاعل مع أزرار الاشتراك الإجباري"""
        bot_username, start_payload = await LinkProcessor.extract_bot_info(link)
        if not bot_username:
            return False, "❌ رابط البوت غير صالح"
        
        if accounts is None:
            accounts = get_active_accounts(user_id)
        
        if not accounts:
            return False, "❌ لا توجد حسابات مسجلة"
        
        command = f"/start {start_payload}" if start_payload else "/start"
        success_count = 0
        failed_count = 0
        
        for phone in accounts:
            try:
                async with TelegramClient(f"echo_ac/{user_id}/{phone}", API_ID, API_HASH, 
                                         device_model="iPhone 15 Pro Max", 
                                         system_version="iOS 17.4") as client:
                    
                    if not await client.is_user_authorized():
                        failed_count += 1
                        continue
                    
                    # إرسال أمر البدء
                    await client.send_message(bot_username, command)
                    await asyncio.sleep(2)
                    
                    # التحقق من وجود أزرار اشتراك إجباري والتعامل معها
                    try:
                        messages = await client.get_messages(bot_username, limit=1)
                        if messages and messages[0].reply_markup:
                            await LinkProcessor._handle_bot_buttons(client, messages[0], bot_username, user_id, phone)
                    except:
                        pass
                    
                    success_count += 1
                    
            except Exception as e:
                failed_count += 1
                await send_telegram_message(user_id, f"📱 {phone}: ❌ فشل - {str(e)[:50]}")
        
        BotAnalytics.track_event('link')
        return True, f"✅ تمت المعالجة!\n📱 ناجح: {success_count}\n❌ فشل: {failed_count}"
    
    @staticmethod
    async def _handle_bot_buttons(client, message, bot_username, user_id, phone):
        """التعامل مع أزرار البوت (اشتراك إجباري، تحقق، إلخ)"""
        try:
            if not message.reply_markup or not message.reply_markup.rows:
                return
            
            for row in message.reply_markup.rows:
                for button in row.buttons:
                    # البحث عن أزرار الاشتراك
                    if button.url and ('t.me/' in button.url):
                        # الانضمام للقناة
                        await LinkProcessor._join_channel_from_url(client, button.url, user_id, phone)
                    
                    # النقر على أزرار التحقق
                    if button.text and any(word in button.text.lower() for word in ['تحقق', 'verify', 'اشتركت', 'joined', 'التالي', 'next']):
                        await message.click(text=button.text)
                        await asyncio.sleep(2)
                        
                        # التحقق من الرسالة التالية
                        next_messages = await client.get_messages(bot_username, limit=1)
                        if next_messages and next_messages[0].reply_markup:
                            await LinkProcessor._handle_bot_buttons(client, next_messages[0], bot_username, user_id, phone)
                        break
        except:
            pass
    
    @staticmethod
    async def _join_channel_from_url(client, url, user_id, phone):
        """الانضمام لقناة من رابط"""
        try:
            try:
                await client(JoinChannelRequest(url))
            except:
                if 't.me/+' in url or 'joinchat/' in url:
                    hash_part = url.split('+')[-1] if '+' in url else url.split('joinchat/')[-1]
                    await client(ImportChatInviteRequest(hash_part))
                else:
                    username = url.split('/')[-1]
                    entity = await client.get_entity(username)
                    await client(JoinChannelRequest(entity))
            
            await send_telegram_message(user_id, f"📱 {phone}: ✅ تم الاشتراك في القناة")
        except Exception as e:
            await send_telegram_message(user_id, f"📱 {phone}: ⚠️ فشل الاشتراك - {str(e)[:30]}")
    
    @staticmethod
    async def process_channel_link(user_id, link, accounts=None):
        """معالجة رابط قناة - انضمام فقط"""
        channel_info = await LinkProcessor.extract_channel_info(link)
        if not channel_info:
            return False, "❌ رابط القناة غير صالح"
        
        if accounts is None:
            accounts = get_active_accounts(user_id)
        
        if not accounts:
            return False, "❌ لا توجد حسابات مسجلة"
        
        success_count = 0
        failed_count = 0
        already_count = 0
        
        for phone in accounts:
            try:
                async with TelegramClient(f"echo_ac/{user_id}/{phone}", API_ID, API_HASH,
                                         device_model="iPhone 15 Pro Max",
                                         system_version="iOS 17.4") as client:
                    
                    if not await client.is_user_authorized():
                        failed_count += 1
                        continue
                    
                    try:
                        if channel_info['type'] == 'invite':
                            await client(ImportChatInviteRequest(channel_info['hash']))
                        else:
                            entity = await client.get_entity(channel_info['username'])
                            await client(JoinChannelRequest(entity))
                        
                        success_count += 1
                        await send_telegram_message(user_id, f"📱 {phone}: ✅ تم الانضمام")
                        
                    except errors.UserAlreadyParticipantError:
                        already_count += 1
                    except Exception as e:
                        failed_count += 1
                        await send_telegram_message(user_id, f"📱 {phone}: ❌ فشل - {str(e)[:30]}")
                    
                    await asyncio.sleep(random.uniform(1, 2))
                    
            except Exception as e:
                failed_count += 1
        
        BotAnalytics.track_event('link')
        return True, f"✅ تمت العملية!\n📱 انضم: {success_count}\nℹ️ عضو مسبقاً: {already_count}\n❌ فشل: {failed_count}"

# ============ نظام التجميع المخصص ============
class CustomCollector:
    """نظام تجميع مخصص لأي بوت"""
    
    @staticmethod
    async def start_custom_collection(user_id, bot_identifier, send_to, accounts=None):
        """بدء تجميع مخصص من أي بوت"""
        if accounts is None:
            accounts = get_active_accounts(user_id)
        
        if not accounts:
            await send_telegram_message(user_id, "❌ لا توجد حسابات مسجلة")
            return
        
        # تنظيف معرف البوت
        bot_username = bot_identifier.lstrip('@').strip()
        
        await send_telegram_message(user_id, f"🤖 بدء التجميع المخصص من @{bot_username}\n📱 عدد الحسابات: {len(accounts)}")
        
        for phone in accounts:
            try:
                async with TelegramClient(f"echo_ac/{user_id}/{phone}", API_ID, API_HASH,
                                         device_model="iPhone 15 Pro Max",
                                         system_version="iOS 17.4") as client:
                    
                    if not await client.is_user_authorized():
                        continue
                    
                    me = await client.get_me()
                    target_id = me.id if send_to == "حساب" else int(user_id) if send_to == "انا" else int(send_to)
                    
                    await send_telegram_message(user_id, f"📱 {phone}: 🔄 بدء التجميع...")
                    
                    # محاولة التفاعل مع البوت
                    await CustomCollector._interact_with_bot(client, bot_username, target_id, user_id, phone)
                    
            except Exception as e:
                await send_telegram_message(user_id, f"📱 {phone}: ❌ خطأ - {str(e)[:50]}")
        
        await send_telegram_message(user_id, "✅ اكتمل التجميع المخصص")
    
    @staticmethod
    async def _interact_with_bot(client, bot_username, target_id, user_id, phone):
        """التفاعل الذكي مع البوت"""
        try:
            # إرسال /start
            await client.send_message(bot_username, f'/start {target_id}')
            await asyncio.sleep(2)
            
            # محاولة التعرف على أزرار البوت
            messages = await client.get_messages(bot_username, limit=1)
            if messages and messages[0].reply_markup:
                await LinkProcessor._handle_bot_buttons(client, messages[0], bot_username, user_id, phone)
            
            # محاولة جمع النقاط
            for _ in range(50):  # 50 محاولة كحد أقصى
                await asyncio.sleep(3)
                messages = await client.get_messages(bot_username, limit=1)
                
                if not messages:
                    break
                
                msg = messages[0]
                msg_text = msg.message or ""
                
                # التحقق من انتهاء القنوات
                if any(word in msg_text for word in ['لا يوجد', 'No channels', 'انتهى', 'finished']):
                    await send_telegram_message(user_id, f"📱 {phone}: ✅ انتهى التجميع")
                    break
                
                # التعامل مع الأزرار
                if msg.reply_markup:
                    await LinkProcessor._handle_bot_buttons(client, msg, bot_username, user_id, phone)
                    
        except Exception as e:
            await send_telegram_message(user_id, f"📱 {phone}: ⚠️ {str(e)[:50]}")

# ============ نظام الإذاعة المتقدم ============
class BroadcastSystem:
    """نظام إذاعة متقدم مع دعم الوسائط والأزرار"""
    
    @staticmethod
    async def send_broadcast(sender_id, message_data, target_type="all", target_ids=None):
        sent_count = 0
        failed_count = 0
        
        targets = []
        
        if target_type == "all":
            for folder in Path("echo_ac").iterdir():
                if folder.is_dir():
                    targets.append(folder.name)
        elif target_type == "admins":
            targets = list(info.get("admins", {}).keys())
            targets.append(str(sudo_id))
        elif target_type == "vips":
            targets = list(info.get("vips", {}).keys())
        elif target_type == "specific" and target_ids:
            targets = target_ids
        
        for user_id in targets:
            try:
                if message_data.get("text"):
                    await send_telegram_message(user_id, message_data["text"])
                    sent_count += 1
                
                if message_data.get("media"):
                    files = {}
                    if message_data["media"].get("photo"):
                        files["photo"] = message_data["media"]["photo"]
                        url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
                        data = {"chat_id": user_id, "caption": message_data.get("caption", "")}
                        requests.post(url, data=data, files=files)
                        sent_count += 1
                    elif message_data["media"].get("video"):
                        files["video"] = message_data["media"]["video"]
                        url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
                        data = {"chat_id": user_id, "caption": message_data.get("caption", "")}
                        requests.post(url, data=data, files=files)
                        sent_count += 1
                    elif message_data["media"].get("document"):
                        files["document"] = message_data["media"]["document"]
                        url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
                        data = {"chat_id": user_id, "caption": message_data.get("caption", "")}
                        requests.post(url, data=data, files=files)
                        sent_count += 1
                
                await asyncio.sleep(0.05)
            except Exception as e:
                failed_count += 1
                print(f"Failed to send broadcast to {user_id}: {e}")
        
        BotAnalytics.track_event('broadcast', count=sent_count)
        
        return sent_count, failed_count

broadcast_system = BroadcastSystem()

def save_info():
    with open("echo_data.json", "w", encoding='utf-8') as json_file:
        json.dump(info, json_file, indent=4, ensure_ascii=False)

try:
    with open("echo_data.json", "r", encoding='utf-8') as json_file:
        info = json.load(json_file)
except (FileNotFoundError, json.JSONDecodeError):
    info = {}

info["sudo"] = sudo_id
info.setdefault("admins", {})
info.setdefault("sleeptime", 20)
info.setdefault("bot_mode", "paid")
info.setdefault("vips", {})
info.setdefault("trial_settings", {"enabled": False, "duration_hours": 2})
info.setdefault("trial_users", {})
save_info()

def measure_performance(func):
    async def wrapper(*args, **kwargs):
        start = datetime.now()
        result = await func(*args, **kwargs)
        elapsed = (datetime.now() - start).total_seconds()
        if elapsed > 1:
            logging.info(f"⚠️ {func.__name__} took {elapsed:.2f}s")
        return result
    return wrapper

async def get_bot_id(client, bot_username):
    try:
        bot_entity = await client.get_entity(bot_username)
        return bot_entity.id
    except:
        return None

async def process_task(client, response, phonex, sudo):
    try:
        if response.get("type") == "link":
            await client(ImportChatInviteRequest(response.get("tg", "")))
            await asyncio.sleep(random.uniform(1, 2))
            
            messages = await client.get_messages(int(response.get("return", "")), limit=10)
            if messages:
                tasks = [
                    client(GetMessagesViewsRequest(
                        peer=int(response.get("return", "")),
                        id=[msg.id for msg in messages],
                        increment=True
                    ))
                ]
                if messages[0]:
                    tasks.append(client(SendReactionRequest(
                        peer=int(response.get("return", "")),
                        msg_id=messages[0].id,
                        big=True,
                        add_to_recent=True,
                        reaction=[types.ReactionEmoji(emoticon='👍')]
                    )))
                await asyncio.gather(*tasks, return_exceptions=True)
        else:
            await client(JoinChannelRequest(response.get("return", "")))
            await asyncio.sleep(random.uniform(1, 2))
            
            entity = await client.get_entity(response.get("return", ""))
            messages = await client.get_messages(entity, limit=10)
            
            if messages:
                await asyncio.gather(
                    client(GetMessagesViewsRequest(
                        peer=response.get("return", ""),
                        id=[msg.id for msg in messages],
                        increment=True
                    )),
                    client(SendReactionRequest(
                        peer=response.get("return", ""),
                        msg_id=messages[0].id,
                        big=True,
                        reaction=[types.ReactionEmoji(emoticon='👍')]
                    )),
                    return_exceptions=True
                )
        return True
    except Exception:
        return False

def calculate_smart_timeout(response, base_time):
    timeout_val = response.get('timeout')
    if timeout_val and str(timeout_val).lower() != 'none':
        return min(int(timeout_val) + random.randint(2, 5), 30)
    return random.randint(int(base_time), int(base_time * 1.2))

async def smart_sleep(client, timeout, sudo, phonex):
    if timeout > 15:
        try:
            await client(UpdateStatusRequest(offline=True))
            await asyncio.sleep(3)
            await client.disconnect()
            await asyncio.sleep(timeout - 6)
            await client.connect()
            await client(UpdateStatusRequest(offline=False))
        except:
            await asyncio.sleep(timeout)
    else:
        await asyncio.sleep(timeout)

async def handle_task_error(error, phonex, sudo):
    if isinstance(error, errors.FloodWaitError):
        wait_time = min(error.seconds, 3600)
        await send_telegram_message(sudo, f"⏳ حظر مؤقت {phonex}: {wait_time}s")
        await asyncio.sleep(wait_time)
    else:
        await asyncio.sleep(5)

async def cleanup_client(phonex, sudo):
    try:
        key = f"{phonex}-{sudo}"
        if key in clients:
            client = clients[key]
            if client.is_connected():
                await client.disconnect()
            del clients[key]
    except:
        pass

@measure_performance
async def background_task(phonex, bot_username, sudo, send_to):
    global clients, points_data
    await send_telegram_message(sudo, f"🔄 جاري الاتصال : {phonex}")
    
    try:
        client = await ConnectionPool.get_client(phonex, sudo)
        clients[f"{phonex}-{sudo}"] = client
        
        @client.on(events.NewMessage)
        async def handle_new_message(event):
            if event.is_channel:
                asyncio.create_task(auto_view_message(client, event))
        
        await client(UpdateStatusRequest(offline=False))
        
        if not await client.is_user_authorized():
            await send_telegram_message(sudo, f"❌ الحساب غير مسجل بالبوت : {phonex}")
            await cleanup_client(phonex, sudo)
            stop_background_task(phonex, sudo)
            return
        
        me = await client.get_me()
        user_id = me.id
        if send_to == "انا":
            send_to = sudo
        elif send_to == "حساب":
            send_to = user_id
        
        bot_id = await get_bot_id(client, bot_username)
        if not bot_id:
            await send_telegram_message(sudo, f"❌ - لا يمكن العثور على البوت بالمعرف '{bot_username}'.\n- {phonex}")
            await cleanup_client(phonex, sudo)
            stop_background_task(phonex, sudo)
            return
        
        await client.send_message(bot_username, '/start')
        await asyncio.sleep(3)
        
        response = await keko_api.request({"login": user_id, "bot_id": bot_id})
        
        if response.get("ok", False):
            echo_token = response.get("token", "")
            await send_telegram_message(sudo, f"✅ - تم تسجيل الدخول بنجاح, توكن حسابك : {echo_token}\n\n- 🎯 ستيم ارسال نقاط الى : {send_to}\n\n- 📱 {phonex}")
            
            fail_count = 0
            while f"{phonex}-{sudo}" in clients:
                response = await keko_api.request({"token": echo_token})
                
                if not response.get("ok", False):
                    msg = response.get('msg', '')
                    if 'تسجيل الدخول' in msg:
                        await send_telegram_message(sudo, f"❌ - {msg}\n\n- {phonex}")
                        break
                    await asyncio.sleep(15)
                    continue
                
                if response.get("canleave", False):
                    for chat in response["canleave"]:
                        try:
                            await client.delete_dialog(chat)
                            await send_telegram_message(sudo, f"🚪 - تم مغادرة : {chat} -> بسبب انتهاء مده الاشتراك\n\n- {phonex}")
                            await asyncio.sleep(random.randint(2, 8))
                        except Exception as e:
                            print(f"Error: {str(e)}")
                
                if response.get("type", "") == "link":
                    try:
                        await client(ImportChatInviteRequest(response.get("tg", "")))
                        await asyncio.sleep(random.randint(1, 3))
                        messages = await client.get_messages(int(response.get("return", "")), limit=20)
                        MSG_IDS = [message.id for message in messages]
                        await asyncio.sleep(random.randint(1, 3))
                        await client(GetMessagesViewsRequest(
                            peer=int(response.get("return", "")),
                            id=MSG_IDS,
                            increment=True
                        ))
                        try:
                            await client(SendReactionRequest(
                                peer=int(response.get("return", "")),
                                msg_id=messages[0].id,
                                big=True,
                                add_to_recent=True,
                                reaction=[types.ReactionEmoji(emoticon='👍')]
                            ))
                        except Exception as e:
                            print(f"Error: {str(e)}")
                    except errors.FloodWaitError as e:
                        await handle_task_error(e, phonex, sudo)
                        continue
                    except Exception as e:
                        await send_telegram_message(sudo, f"⚠️ - خطا، سيتم تخطي المهمة الحالية: \n\n{str(e)}\n\n- {phonex}")
                        await asyncio.sleep(8)
                        continue
                else:
                    try:
                        await client(JoinChannelRequest(response.get("return", "")))
                        await asyncio.sleep(random.randint(1, 3))
                        entity = await client.get_entity(response.get("return", ""))
                        await asyncio.sleep(random.randint(1, 3))
                        messages = await client.get_messages(entity, limit=10)
                        await asyncio.sleep(random.randint(1, 3))
                        MSG_IDS = [message.id for message in messages]
                        await client(GetMessagesViewsRequest(
                            peer=response.get("return", ""),
                            id=MSG_IDS,
                            increment=True
                        ))
                        try:
                            await client(SendReactionRequest(
                                peer=response.get("return", ""),
                                msg_id=messages[0].id,
                                big=True,
                                add_to_recent=True,
                                reaction=[types.ReactionEmoji(emoticon='👍')]
                            ))
                        except Exception as e:
                            print(f"Error: {str(e)}")
                    except errors.FloodWaitError as e:
                        await handle_task_error(e, phonex, sudo)
                        continue
                    except Exception as e:
                        await send_telegram_message(sudo, f"⚠️ - خطا، سيتم تخطي المهمة الحالية: \n\n{str(e)}\n\n- {phonex}")
                        await asyncio.sleep(8)
                        continue
                
                response = await keko_api.request({"token": echo_token, "to_id": send_to, "done": response.get('return', '')})
                
                if not response.get("ok", False):
                    msg = response.get('msg', '')
                    await send_telegram_message(sudo, f"❌ - {msg}\n\n- {phonex}")
                    if 'تسجيل الدخول' in msg:
                        break
                else:
                    points_val = response.get('c')
                    if points_val is not None:
                        points_data.setdefault(sudo, {})[phonex] = points_val
                    
                    points_text = ""
                    if points_val is not None and points_val != 0:
                        points_text = f"💰 - اصبح عدد نقاطك: {points_val}\n\n"
                    
                    timeout_val = response.get('timeout')
                    leave_after_text = "غير محدد"
                    if timeout_val is not None and str(timeout_val).lower() != 'none':
                        leave_after_text = f"{timeout_val} ثانية"
                    
                    timeoutt = random.randint(int(info["sleeptime"]), int(info["sleeptime"] * 1.3))
                    await send_telegram_message(sudo, f"{points_text}⏱️ يمكنك المغادرة بعد: {leave_after_text}\n\n📱 - {phonex}\n\n⏳ - انتظار: {timeoutt}")
                    
                    BotAnalytics.track_event('task')
                
                await smart_sleep(client, timeoutt, sudo, phonex)
        else:
            await send_telegram_message(sudo, f"❌ - {response.get('msg', '')}\n\n- {phonex}")
        
        await cleanup_client(phonex, sudo)
        await send_telegram_message(sudo, f"🛑 - تم ايقاف عمل الرقم : {phonex}")
        stop_background_task(phonex, sudo)
        
    except Exception as e:
        await send_telegram_message(sudo, f"⚠️ حدث خطا في الحساب : {phonex}")
        await cleanup_client(phonex, sudo)
        stop_background_task(phonex, sudo)

async def auto_view_message(client, event):
    try:
        await asyncio.sleep(random.uniform(0.5, 1.5))
        await client(GetMessagesViewsRequest(
            peer=event.chat_id,
            id=[event.message.id],
            increment=True
        ))
    except:
        pass

def start_background_task(phone, bot_username, chat_id, send_to, duration_seconds=None):
    chat_id = str(chat_id)
    phone = str(phone)
    stop_background_task(phone, chat_id)
    if chat_id not in running_processes:
        running_processes[chat_id] = {}
    if phone not in running_processes[chat_id]:
        task = asyncio.create_task(background_task(phone, bot_username, chat_id, send_to))
        running_processes[chat_id][phone] = task
        
        if duration_seconds and duration_seconds > 0:
            async def stop_after_delay(delay, p, c):
                await asyncio.sleep(delay)
                if c in running_processes and p in running_processes[c]:
                    stop_background_task(p, c)
                    await send_telegram_message(c, f"⏰ انتهت مدة التجميع المحددة للحساب: {p}\nتم إيقافه تلقائياً.")
            
            asyncio.create_task(stop_after_delay(duration_seconds, phone, chat_id))

def stop_all_background_tasks(chat_id):
    chat_id = str(chat_id)
    if chat_id in running_processes:
        for key, task in list(running_processes[chat_id].items()):
            if key.startswith('custom_'):
                if not task.done():
                    task.cancel()
                print(f"Stopped custom task {key} for chat_id {chat_id}")
            else:
                stop_background_task(key, chat_id)
        running_processes.pop(chat_id, None)
    else:
        print(f"No running tasks found for chat_id {chat_id}.")

def stop_background_task(phone, chat_id):
    global clients
    chat_id = str(chat_id)
    phone = str(phone)
    client_key = f"{phone}-{chat_id}"
    if client_key in clients:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(clients[client_key].disconnect())
            else:
                asyncio.run(clients[client_key].disconnect())
        except Exception as e:
            print(f"Error disconnecting client {client_key}: {e}")
        del clients[client_key]
    
    if chat_id in running_processes and phone in running_processes[chat_id]:
        task = running_processes[chat_id][phone]
        if not task.done():
            task.cancel()
            print(f"Stopped background task for phone {phone} and chat_id {chat_id}")
        else:
            print(f"Background task for phone {phone} and chat_id {chat_id} was not running.")
        running_processes[chat_id].pop(phone, None)
    else:
        print(f"No background task found for phone {phone} and chat_id {chat_id}.")

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

if not os.path.isdir("echo_ac"):
    os.makedirs("echo_ac")

def check_access(user_id):
    user_id_str = str(user_id)
    
    if user_id_str == str(info.get("sudo")):
        return True
    
    if user_id_str in info.get("admins", {}):
        return True
    
    if info.get("bot_mode") == "free":
        return True
    
    if user_id_str in info.get("vips", {}):
        expiration = info["vips"][user_id_str]
        if datetime.now().timestamp() < expiration:
            return True
        else:
            del info["vips"][user_id_str]
            save_info()
    
    if user_id_str in info.get("trial_users", {}):
        expiration = info["trial_users"][user_id_str]
        if datetime.now().timestamp() < expiration:
            return True
        else:
            del info["trial_users"][user_id_str]
            save_info()
            asyncio.create_task(send_telegram_message(user_id_str, "⏰ لقد انتهت فترتك التجريبية."))
    
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global what_need_to_do_echo, points_data
    if not update.message or update.message.chat.type != "private":
        return
    
    chat_id = update.message.chat.id
    chat_id_str = str(chat_id)
    
    BotAnalytics.track_event('user_active', chat_id_str)
    
    if not check_access(chat_id):
        trial_settings = info.get("trial_settings", {})
        if trial_settings.get("enabled") and chat_id_str not in info.get("trial_users", {}):
            duration_hours = trial_settings.get("duration_hours", 2)
            expiration_time = datetime.now() + timedelta(hours=duration_hours)
            info["trial_users"][chat_id_str] = expiration_time.timestamp()
            save_info()
            await update.message.reply_text(f"🎉 مرحباً بك! لقد حصلت على فترة تجريبية لمدة {duration_hours} ساعة لاستخدام البوت.")
        else:
            await update.message.reply_text("❌ عذراً، ليس لديك صلاحية لاستخدام هذا البوت.")
            return
    
    if not os.path.isdir(f"echo_ac/{chat_id_str}"):
        os.makedirs(f"echo_ac/{chat_id_str}")
    
    what_need_to_do_echo[chat_id_str] = ""
    
    user_name = update.message.from_user.first_name
    num_accounts = len(get_active_accounts(chat_id_str))
    running_count = len(get_running_accounts(chat_id_str))
    user_points = points_data.get(chat_id_str, {})
    total_points = sum(user_points.values())
    speed = info['sleeptime']
    
    reply_text = (
        f"👋 أهلاً بك، {user_name}!\n\n"
        f"⚡ سرعة التجميع: {speed} ثانية\n"
        f"📱 عدد الأرقام: {num_accounts}\n"
        f"🟢 قيد التشغيل: {running_count}\n"
        f"💰 النقاط المجمعة: {total_points}"
    )
    
    is_sudo = chat_id_str == str(info["sudo"])
    keyboard = [
        [InlineKeyboardButton("➕ اضافه رقم", callback_data="addecho"), InlineKeyboardButton("➖ مسح رقم", callback_data="delecho")],
        [InlineKeyboardButton("📱 الارقام الخاصه بك", callback_data="myecho"), InlineKeyboardButton("💰 عدد نقاطك", callback_data="mypoints")],
        [InlineKeyboardButton("📢 رشق قناة", callback_data="joinchn"), InlineKeyboardButton("🔗 دخول رابط دعوة", callback_data="join_invite_link")],
        [InlineKeyboardButton("👍 رشق تصويت", callback_data="boost_vote"), InlineKeyboardButton("👁️ رشق مشاهدات", callback_data="boost_views")],
        [InlineKeyboardButton("📊 رشق استفسار", callback_data="boost_poll"), InlineKeyboardButton("💬 إرسال سبام", callback_data="spam_message")],
        [InlineKeyboardButton("🚪 مغادرة قناة", callback_data="leave_specific_chn"), InlineKeyboardButton("🗑️ مسح كل القنوات", callback_data="leavechn")],
        [InlineKeyboardButton("📅 مسح قنوات (+7 ايام)", callback_data="leave_7d_collection"), InlineKeyboardButton("⚙️ سرعة التجميع", callback_data="sleeptime")],
        [InlineKeyboardButton("🔄 تحويل تمبلر", callback_data="templer"), InlineKeyboardButton("🤖 تجميع النقاط", callback_data="custom_collect")],
        [InlineKeyboardButton("🎯 تجميع مخصص", callback_data="custom_collect_new")],
        [InlineKeyboardButton("▶️ تشغيل الكل", callback_data="start_all"), InlineKeyboardButton("⏹️ إيقاف الكل", callback_data="stop_all")],
        [InlineKeyboardButton("🛑 إيقاف كل التجميع", callback_data="stop_all_collection")],
    ]
    
    if is_sudo:
        keyboard.append([InlineKeyboardButton("👑 اضافه ادمن", callback_data="addadminecho"), InlineKeyboardButton("❌ مسح ادمن", callback_data="deladminecho")])
        keyboard.append([InlineKeyboardButton("💾 ملف ارقام", callback_data="copynum"), InlineKeyboardButton("⚠️ مسح جميع الحسابات", callback_data="delall")])
        keyboard.append([InlineKeyboardButton("📢 إذاعة", callback_data="broadcast_menu"), InlineKeyboardButton("📊 إحصائيات", callback_data="bot_stats")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(reply_text, reply_markup=reply_markup)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id_str = str(update.message.chat.id)
    if chat_id_str != str(info["sudo"]):
        return
    
    mode_text = "🌍 مجاني للكل" if info.get("bot_mode") == "free" else "💎 مدفوع (للمشتركين فقط)"
    trial_text = "✅ مفعلة" if info.get("trial_settings", {}).get("enabled") else "❌ معطلة"
    trial_duration = info.get("trial_settings", {}).get("duration_hours", 2)
    
    keyboard = [
        [InlineKeyboardButton(f"🔄 وضع البوت: {mode_text}", callback_data="toggle_mode")],
        [InlineKeyboardButton("👑 إدارة عضوية VIP", callback_data="manage_vip")],
        [InlineKeyboardButton(f"🎁 الفترة التجريبية: {trial_text}", callback_data="toggle_trial")],
        [InlineKeyboardButton(f"⏱️ مدة التجربة: {trial_duration} ساعات", callback_data="set_trial_duration")],
        [InlineKeyboardButton("📢 لوحة الإذاعة", callback_data="broadcast_menu")],
        [InlineKeyboardButton("📊 إحصائيات البوت", callback_data="bot_stats")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("⚙️ لوحة تحكم المطور", reply_markup=reply_markup)

async def broadcast_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    chat_id_str = str(query.message.chat.id)
    if chat_id_str != str(info["sudo"]):
        return
    
    keyboard = [
        [InlineKeyboardButton("📢 إذاعة للجميع", callback_data="broadcast_all")],
        [InlineKeyboardButton("👑 إذاعة للأدمنز", callback_data="broadcast_admins")],
        [InlineKeyboardButton("💎 إذاعة للـ VIP", callback_data="broadcast_vips")],
        [InlineKeyboardButton("📝 إذاعة نصية", callback_data="broadcast_text")],
        [InlineKeyboardButton("🖼 إذاعة مع صورة", callback_data="broadcast_photo")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel_home")]
    ]
    
    stats = BotAnalytics.stats
    text = f"""
📢 **لوحة الإذاعة المتقدمة**

📊 **إحصائيات الإذاعات:**
- عدد الإذاعات المرسلة: {stats['broadcasts_sent']}
- إجمالي المستلمين: {stats['broadcast_recipients']}

👥 **إحصائيات المستخدمين:**
- الأدمنز: {len(info.get('admins', {}))}
- VIP: {len(info.get('vips', {}))}
- المجلدات الكلية: {len([f for f in Path('echo_ac').iterdir() if f.is_dir()])}
    """.strip()
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def bot_stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    chat_id_str = str(query.message.chat.id)
    if chat_id_str != str(info["sudo"]):
        return
    
    total_folders = len([f for f in Path('echo_ac').iterdir() if f.is_dir()])
    total_sessions = 0
    for folder in Path('echo_ac').iterdir():
        if folder.is_dir():
            total_sessions += len([f for f in folder.glob('*.session')])
    
    stats_text = BotAnalytics.get_stats()
    additional_stats = f"""

📁 **إحصائيات التخزين:**
- مجلدات المستخدمين: {total_folders}
- إجمالي الجلسات: {total_sessions}

⚙️ **إعدادات النظام:**
- سرعة التجميع: {info['sleeptime']} ثانية
- وضع البوت: {'مجاني' if info.get('bot_mode') == 'free' else 'مدفوع'}
- الفترة التجريبية: {'مفعلة' if info.get('trial_settings', {}).get('enabled') else 'معطلة'}
🔗 **الروابط المعالجة:** {BotAnalytics.stats['links_processed']}
    """
    
    keyboard = [[InlineKeyboardButton("🔄 تحديث", callback_data="bot_stats"),
                 InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel_home")]]
    
    await query.edit_message_text(stats_text + additional_stats, reply_markup=InlineKeyboardMarkup(keyboard))

def contact_validate(text):
    text = str(text)
    return len(text) > 0 and text[0] == '+' and text[1:].isdigit()

async def delall(chat_id):
    directory = f'echo_ac/{chat_id}'
    stop_all_background_tasks(chat_id)
    if os.path.isdir(directory):
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                    await send_telegram_message(chat_id, f"📱 الرقم : {filename.replace('.session', '')}\n✅ تم حذفه")
            except Exception as e:
                print(f'Failed to delete {file_path}. Reason: {e}')

async def copynum(chat_id):
    directory = f'echo_ac/{chat_id}'
    if os.path.isdir(directory):
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            if os.path.isfile(file_path) and filename.endswith('.session'):
                with open(file_path, 'rb') as f:
                    await send_file(bot_token, chat_id, filename, f)

async def send_file(bot_token, chat_id, file_name, file_data):
    requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendDocument",
        data={"chat_id": chat_id, "caption": f"📱 الرقم : {file_name.replace('.session', '')}"},
        files={"document": (file_name, file_data)}
    )

async def joinchn(id, chn):
    accounts = get_active_accounts(id)
    for file_stem in accounts:
        async with TelegramClient(f"echo_ac/{id}/{file_stem}", API_ID, API_HASH, device_model="iPhone 15 Pro Max", system_version="iOS 17.4") as client:
            try:
                await client(JoinChannelRequest(chn))
                await send_telegram_message(id, f"📱 الرقم : {file_stem}\n✅ تم الانضمام في {chn}")
            except Exception as e:
                await send_telegram_message(id, f"📱 الرقم : {file_stem}\n❌ فشل في الانضمام: {e}")
            await asyncio.sleep(random.randint(1, 2))

async def leave_a_channel(id, chn):
    accounts = get_active_accounts(id)
    for file_stem in accounts:
        async with TelegramClient(f"echo_ac/{id}/{file_stem}", API_ID, API_HASH, device_model="iPhone 15 Pro Max", system_version="iOS 17.4") as client:
            try:
                await client(LeaveChannelRequest(chn))
                await send_telegram_message(id, f"📱 الرقم : {file_stem}\n✅ تمت المغادرة من {chn}")
            except Exception as e:
                await send_telegram_message(id, f"📱 الرقم : {file_stem}\n❌ فشل في المغادرة: {e}")
            await asyncio.sleep(random.randint(1, 2))

async def boost_post_vote(user_id, post_link):
    try:
        parts = post_link.strip().split('/')
        channel_username = parts[-2]
        msg_id = int(parts[-1])
    except (IndexError, ValueError):
        await send_telegram_message(user_id, "❌ فشل تحليل الرابط. تأكد من أن الرابط بالشكل الصحيح (e.g., https://t.me/channel/123).")
        return
    
    accounts = get_active_accounts(user_id)
    for file_stem in accounts:
        async with TelegramClient(f"echo_ac/{user_id}/{file_stem}", API_ID, API_HASH, device_model="iPhone 15 Pro Max", system_version="iOS 17.4") as client:
            try:
                channel_entity = await client.get_entity(channel_username)
                await client(SendReactionRequest(
                    peer=channel_entity,
                    msg_id=msg_id,
                    big=True,
                    add_to_recent=True,
                    reaction=[types.ReactionEmoji(emoticon='👍')]
                ))
                await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n✅ تم التصويت بنجاح.")
            except errors.UserNotParticipantError:
                await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n⚠️ فشل: الحساب ليس عضواً في القناة.")
            except Exception as e:
                error_message = str(e).replace('<', '').replace('>', '')
                await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n❌ فشل التصويت: {error_message}")
            await asyncio.sleep(random.randint(1, 3))

async def boost_post_views(user_id, post_link):
    try:
        parts = post_link.strip().split('/')
        channel_username = parts[-2]
        msg_id = int(parts[-1])
    except (IndexError, ValueError):
        await send_telegram_message(user_id, "❌ فشل تحليل الرابط. تأكد من أن الرابط بالشكل الصحيح (e.g., https://t.me/channel/123).")
        return
    
    accounts = get_active_accounts(user_id)
    for file_stem in accounts:
        async with TelegramClient(f"echo_ac/{user_id}/{file_stem}", API_ID, API_HASH, device_model="iPhone 15 Pro Max", system_version="iOS 17.4") as client:
            try:
                peer = await client.get_entity(channel_username)
                await client(GetMessagesViewsRequest(
                    peer=peer,
                    id=[msg_id],
                    increment=True
                ))
                await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n✅ تمت المشاهدة بنجاح.")
            except errors.UserNotParticipantError:
                await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n⚠️ فشل: الحساب ليس عضواً في القناة. يجب الانضمام أولاً.")
            except Exception as e:
                error_message = str(e).replace('<', '').replace('>', '')
                await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n❌ فشل زيادة المشاهدات: {error_message}")
            await asyncio.sleep(random.randint(1, 2))

async def boost_poll_vote(user_id, post_link, option_index):
    try:
        option_index_0_based = option_index - 1
        if option_index_0_based < 0:
            await send_telegram_message(user_id, "❌ رقم الخيار يجب أن يكون 1 أو أكبر.")
            return
        
        parts = post_link.strip().split('/')
        channel_username = parts[-2]
        msg_id = int(parts[-1])
    except (IndexError, ValueError):
        await send_telegram_message(user_id, "❌ فشل تحليل الرابط. تأكد من أن الرابط بالشكل الصحيح (e.g., https://t.me/channel/123).")
        return
    
    accounts = get_active_accounts(user_id)
    for file_stem in accounts:
        async with TelegramClient(f"echo_ac/{user_id}/{file_stem}", API_ID, API_HASH, device_model="iPhone 15 Pro Max", system_version="iOS 17.4") as client:
            try:
                peer = await client.get_entity(channel_username)
                message = await client.get_messages(peer, ids=msg_id)
                if not message or not message.media or not isinstance(message.media, MessageMediaPoll):
                    await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n❌ فشل: المنشور المحدد ليس استفتاءً أو لا يمكن الوصول إليه.")
                    continue
                
                poll = message.media.poll
                if option_index_0_based >= len(poll.answers):
                    await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n❌ فشل: رقم الخيار ({option_index}) غير موجود في الاستفتاء.")
                    continue
                
                option_to_vote = poll.answers[option_index_0_based].option
                
                await client(SendVoteRequest(
                    peer=peer,
                    msg_id=msg_id,
                    options=[option_to_vote]
                ))
                await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n✅ تم التصويت على الخيار {option_index} بنجاح.")
            except errors.UserNotParticipantError:
                await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n⚠️ فشل: الحساب ليس عضواً في القناة. يجب الانضمام أولاً.")
            except errors.PollVoteRequiredError:
                await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n⚠️ فشل: لا يمكنك التصويت في هذا الاستفتاء.")
            except Exception as e:
                error_message = str(e).replace('<', '').replace('>', '')
                await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n❌ فشل التصويت: {error_message}")
            await asyncio.sleep(random.randint(1, 3))

async def spam_messages(user_id, spam_details, count, target_username):
    file_path = spam_details.get("file_path")
    spam_text = spam_details.get("text")
    
    accounts = get_active_accounts(user_id)
    if not accounts:
        await send_telegram_message(user_id, "❌ لا يوجد حسابات مسجلة لبدء الإرسال.")
        return
    
    num_accounts = len(accounts)
    count_per_account = (count + num_accounts - 1) // num_accounts
    total_sent = 0
    
    await send_telegram_message(user_id, f"✅ تم استلام المعلومات. سيبدأ الإرسال إلى {target_username}.\n📊 - إجمالي الرسائل: {count}\n📱 - عدد الحسابات: {num_accounts}\n📨 - رسائل لكل حساب: ~{count_per_account}")
    
    try:
        for file_stem in accounts:
            if total_sent >= count:
                break
            
            async with TelegramClient(f"echo_ac/{user_id}/{file_stem}", API_ID, API_HASH, device_model="iPhone 15 Pro Max", system_version="iOS 17.4") as client:
                try:
                    target_entity = await client.get_entity(target_username)
                    await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n🔄 - بدأ الإرسال...")
                    
                    sent_by_this_account = 0
                    for i in range(count_per_account):
                        if total_sent >= count:
                            break
                        
                        try:
                            if file_path:
                                await client.send_file(target_entity, file=file_path, caption=spam_text or "")
                            elif spam_text:
                                await client.send_message(target_entity, message=spam_text)
                            else:
                                continue
                            
                            total_sent += 1
                            sent_by_this_account += 1
                            await asyncio.sleep(random.uniform(1, 2))
                        except errors.FloodWaitError as e:
                            await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n⏳ - تم حظره مؤقتًا. الانتظار لمدة {e.seconds} ثانية.")
                            await asyncio.sleep(e.seconds + 5)
                        except Exception as inner_e:
                            await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n❌ - فشل في إرسال الرسالة: {inner_e}")
                            break
                    
                    await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n✅ - اكتمل إرسال {sent_by_this_account} رسالة.")
                except Exception as e:
                    error_message = str(e).replace('<', '').replace('>', '')
                    await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n❌ فشل الإرسال: {error_message}")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
    
    await send_telegram_message(user_id, f"🏁 انتهت عملية السبام. تم إرسال {total_sent}/{count} رسالة.")

async def echoMaker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global what_need_to_do_echo, info
    if not update.message or update.message.chat.type != "private":
        return
    
    chat_id_str = str(update.message.chat.id)
    
    if not check_access(chat_id_str):
        return
    
    if chat_id_str in what_need_to_do_echo and what_need_to_do_echo[chat_id_str] == "get_spam_message":
        spam_info = {"text": None, "file_path": None}
        message = update.message
        
        media_file_id = None
        if message.photo:
            media_file_id = message.photo[-1].file_id
        elif message.document:
            media_file_id = message.document.file_id
        elif message.video:
            media_file_id = message.video.file_id
        elif message.audio:
            media_file_id = message.audio.file_id
        elif message.voice:
            media_file_id = message.voice.file_id
        
        spam_info["text"] = message.text or message.caption
        
        if media_file_id:
            try:
                new_file = await context.bot.get_file(media_file_id)
                temp_dir = Path("temp_spam")
                temp_dir.mkdir(exist_ok=True)
                file_path = temp_dir / f"{chat_id_str}_{Path(new_file.file_path).name}"
                await new_file.download_to_drive(custom_path=file_path)
                spam_info["file_path"] = str(file_path)
            except Exception as e:
                await update.message.reply_text(f"❌ حدث خطأ أثناء معالجة الملف: {e}")
                what_need_to_do_echo[chat_id_str] = ""
                return
        
        if not spam_info["text"] and not spam_info["file_path"]:
            await update.message.reply_text("❌ لا يمكن إرسال هذه الرسالة (فارغة أو نوع غير مدعوم).")
            what_need_to_do_echo[chat_id_str] = ""
            return
        
        what_need_to_do_echo[f"{chat_id_str}_spam_details"] = spam_info
        what_need_to_do_echo[chat_id_str] = "get_spam_count"
        await update.message.reply_text("✅ تم حفظ الرسالة. الآن أرسل عدد المرات التي تريد تكرارها:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
        return
    
    # معالجة الإذاعة
    if chat_id_str in what_need_to_do_echo and what_need_to_do_echo[chat_id_str].startswith("broadcast_"):
        action = what_need_to_do_echo[chat_id_str]
        message = update.message
        
        if action == "broadcast_text_get":
            text = message.text
            target_type = what_need_to_do_echo.get(f"{chat_id_str}_broadcast_target", "all")
            
            what_need_to_do_echo[chat_id_str] = ""
            
            await update.message.reply_text("🔄 جاري إرسال الإذاعة...")
            
            message_data = {"text": text}
            sent, failed = await broadcast_system.send_broadcast(chat_id_str, message_data, target_type)
            
            await update.message.reply_text(
                f"✅ تم إرسال الإذاعة!\n\n"
                f"📊 الإحصائيات:\n"
                f"✅ ناجح: {sent}\n"
                f"❌ فشل: {failed}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="broadcast_menu")]])
            )
        
        elif action == "broadcast_photo_get":
            media_file_id = None
            if message.photo:
                media_file_id = message.photo[-1].file_id
            elif message.document:
                media_file_id = message.document.file_id
            elif message.video:
                media_file_id = message.video.file_id
            
            if media_file_id:
                caption = message.caption or ""
                target_type = what_need_to_do_echo.get(f"{chat_id_str}_broadcast_target", "all")
                
                what_need_to_do_echo[chat_id_str] = ""
                
                await update.message.reply_text("🔄 جاري إرسال الإذاعة...")
                
                message_data = {
                    "text": caption,
                    "media": {"photo": media_file_id}
                }
                sent, failed = await broadcast_system.send_broadcast(chat_id_str, message_data, target_type)
                
                await update.message.reply_text(
                    f"✅ تم إرسال الإذاعة!\n\n"
                    f"📊 الإحصائيات:\n"
                    f"✅ ناجح: {sent}\n"
                    f"❌ فشل: {failed}",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="broadcast_menu")]])
                )
            else:
                await update.message.reply_text("❌ الرجاء إرسال صورة أو ملف.")
        
        return
    
    # معالجة الروابط
    if chat_id_str in what_need_to_do_echo and what_need_to_do_echo[chat_id_str] == "get_link_type":
        link = update.message.text.strip()
        link_type = await LinkProcessor.detect_link_type(link)
        
        if link_type == 'unknown':
            await update.message.reply_text(
                "❌ الرابط غير معروف. الرجاء إرسال رابط تليجرام صحيح.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]])
            )
            return
        
        what_need_to_do_echo[f"{chat_id_str}_link"] = link
        what_need_to_do_echo[chat_id_str] = "get_accounts_for_link"
        
        accounts = get_active_accounts(chat_id_str)
        running = get_running_accounts(chat_id_str)
        
        keyboard = [
            [InlineKeyboardButton("📱 جميع الحسابات", callback_data="link_all")],
            [InlineKeyboardButton("🟢 الحسابات قيد التشغيل فقط", callback_data="link_running")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]
        ]
        
        await update.message.reply_text(
            f"✅ تم التعرف على الرابط: **{link_type}**\n\n"
            f"📊 لديك {len(accounts)} حساب مسجل\n"
            f"🟢 {len(running)} حساب قيد التشغيل\n\n"
            f"اختر الحسابات المراد استخدامها:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # معالجة التجميع المخصص
    if chat_id_str in what_need_to_do_echo and what_need_to_do_echo[chat_id_str] == "get_custom_bot":
        bot_identifier = update.message.text.strip()
        what_need_to_do_echo[f"{chat_id_str}_custom_bot"] = bot_identifier
        what_need_to_do_echo[chat_id_str] = "get_custom_send_to"
        
        await update.message.reply_text(
            "🎯 ارسل ايدي الحساب الذي تريد التجميع له نقاط:\n\n"
            "- ارسل 'انا' لارسال النقاط لحسابك\n"
            "- ارسل 'حساب' لارسال النقاط لنفس الحساب",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]])
        )
        return
    
    if chat_id_str in what_need_to_do_echo and what_need_to_do_echo[chat_id_str] == "get_custom_send_to":
        send_to = update.message.text.strip()
        bot_identifier = what_need_to_do_echo.get(f"{chat_id_str}_custom_bot")
        what_need_to_do_echo[chat_id_str] = ""
        
        await update.message.reply_text(
            f"🔄 جاري بدء التجميع المخصص من {bot_identifier}...",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]])
        )
        
        asyncio.create_task(CustomCollector.start_custom_collection(chat_id_str, bot_identifier, send_to))
        return
    
    text = update.message.text
    if not text:
        return
    
    if text.startswith("/run ") or text.startswith("/stop "):
        return
    
    if chat_id_str in what_need_to_do_echo and what_need_to_do_echo[chat_id_str]:
        action = what_need_to_do_echo[chat_id_str]
        
        if action == "addecho":
            if not contact_validate(text):
                await update.message.reply_text("❌ ارسل رقم صحيح", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
                return
            client = TelegramClient(f"echo_ac/{chat_id_str}/{text}", API_ID, API_HASH, device_model="iPhone 15 Pro Max", system_version="iOS 17.4")
            try:
                await client.connect()
                what_need_to_do_echo[f"{chat_id_str}:phone"] = text
                sent_code = await client.send_code_request(text)
                what_need_to_do_echo[f"{chat_id_str}:phone_code_hash"] = sent_code.phone_code_hash
                what_need_to_do_echo[chat_id_str] = "echocode"
                await update.message.reply_text("📱 ارسل رمز تسجيل الدخول:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
            except Exception as e:
                what_need_to_do_echo[chat_id_str] = ""
                await update.message.reply_text(f"❌ حدث خطأ: {e}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
            finally:
                if client.is_connected():
                    await client.disconnect()
        
        elif action == "echocode":
            what_need_to_do_echo[f"{chat_id_str}code"] = text
            what_need_to_do_echo[chat_id_str] = "anthercode"
            await update.message.reply_text("🔐 ارسل رمز التحقق بخطوتين (اذا لم يكن هناك رمز ارسل اي شيء):")
        
        elif action == "anthercode":
            phone = what_need_to_do_echo.get(f"{chat_id_str}:phone")
            code = what_need_to_do_echo.get(f"{chat_id_str}code")
            phone_code_hash = what_need_to_do_echo.get(f"{chat_id_str}:phone_code_hash")
            client = TelegramClient(f"echo_ac/{chat_id_str}/{phone}", API_ID, API_HASH, device_model="iPhone 15 Pro Max", system_version="iOS 17.4")
            try:
                await client.connect()
                await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
                await update.message.reply_text(f"✅ تم تسجيل الدخول بنجاح: {phone}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
                SessionManager.invalidate(chat_id_str)
            except errors.SessionPasswordNeededError:
                await client.sign_in(password=text)
                await update.message.reply_text(f"✅ تم تسجيل الدخول بنجاح: {phone}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
                SessionManager.invalidate(chat_id_str)
            except Exception as e:
                await update.message.reply_text(f"❌ حدث خطأ: {e}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
            finally:
                what_need_to_do_echo[chat_id_str] = ""
                if client.is_connected():
                    await client.disconnect()
        
        elif action.startswith("collect_bot_user:"):
            parts = action.split(":")
            target = parts[1]
            duration = parts[2]
            bot_user = text.lstrip('@')
            what_need_to_do_echo[chat_id_str] = f"collect_send_to:{target}:{duration}:{bot_user}"
            await update.message.reply_text(
                "🎯 ارسل ايدي الحساب الذي تريد التجميع له نقاط:\n\n"
                "- ارسل 'انا' لارسال النقاط لحسابك\n"
                "- ارسل 'حساب' لارسال النقاط لنفس الحساب",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="myecho")]]))
        
        elif action.startswith("collect_send_to:"):
            parts = action.split(":")
            target = parts[1]
            duration_seconds = int(parts[2])
            bot_user = parts[3]
            send_to = text
            what_need_to_do_echo[chat_id_str] = ""
            
            if target == "all":
                await update.message.reply_text(f"✅ تم بدء التجميع لجميع الحسابات لمدة محددة.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
                for filename in get_active_accounts(chat_id_str):
                    start_background_task(filename, bot_user, chat_id_str, send_to, duration_seconds)
            else:
                filename = target
                await update.message.reply_text(f"✅ تم بدء التجميع للحساب {filename} لمدة محددة.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
                start_background_task(filename, bot_user, chat_id_str, send_to, duration_seconds)
        
        elif action.startswith("custom_collect_send_to:"):
            parts = action.split(":")
            bot_type = parts[1]
            duration_seconds = int(parts[2])
            send_to = text
            what_need_to_do_echo[chat_id_str] = ""
            
            bot_name = ""
            if bot_type == "mahdaweon":
                bot_name = "المهدويون"
            elif bot_type == "damkom":
                bot_name = "دعمكم"
            elif bot_type == "asiasell":
                bot_name = "اساسيل"
            elif bot_type == "billion":
                bot_name = "المليار"
            elif bot_type == "cr7":
                bot_name = "كرستيانو"
            elif bot_type == "joker":
                bot_name = "الجوكر"
            
            await update.message.reply_text(f"✅ تم بدء التجميع من بوت {bot_name} لمدة محددة. سيتم إيقافه تلقائياً بعد انتهاء الوقت.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
            
            collection_task = None
            if chat_id_str not in running_processes:
                running_processes[chat_id_str] = {}
            
            task_key = f'custom_{bot_type}'
            
            if bot_type == 'mahdaweon':
                collection_task = asyncio.create_task(run_mahdaweon_collector_for_all_accounts(chat_id_str, send_to))
            elif bot_type == 'damkom':
                collection_task = asyncio.create_task(run_damkom_collector_for_all_accounts(chat_id_str, send_to))
            elif bot_type == 'asiasell':
                collection_task = asyncio.create_task(run_asiasell_collector_for_all_accounts(chat_id_str, send_to))
            elif bot_type == 'billion':
                collection_task = asyncio.create_task(run_billion_collector_for_all_accounts(chat_id_str, send_to))
            elif bot_type == 'cr7':
                collection_task = asyncio.create_task(run_cr7_collector_for_all_accounts(chat_id_str, send_to))
            elif bot_type == 'joker':
                collection_task = asyncio.create_task(run_joker_collector_for_all_accounts(chat_id_str, send_to))
            
            if collection_task:
                running_processes[chat_id_str][task_key] = collection_task
                
                async def stop_after_delay(task, delay, user_id, bot_name_text, t_key):
                    try:
                        await asyncio.sleep(delay)
                        if user_id in running_processes and t_key in running_processes[user_id]:
                            if not task.done():
                                task.cancel()
                            running_processes[user_id].pop(t_key, None)
                            await send_telegram_message(user_id, f"⏰ انتهت مدة التجميع المحددة من بوت {bot_name_text}. تم إيقافه.")
                    except asyncio.CancelledError:
                        pass
                
                asyncio.create_task(stop_after_delay(collection_task, duration_seconds, chat_id_str, bot_name, task_key))
        
        elif action == "get_spam_count":
            try:
                count = int(text)
                if count <= 0:
                    await update.message.reply_text("❌ الرجاء إدخال عدد أكبر من صفر.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
                    return
                what_need_to_do_echo[f"{chat_id_str}_spam_count"] = count
                what_need_to_do_echo[chat_id_str] = "get_spam_target"
                await update.message.reply_text(f"📊 سيتم تكرار الرسالة {count} مرة.\n\nالآن أرسل يوزر المجموعة أو الشخص المستهدف (مثال: @username):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
            except ValueError:
                await update.message.reply_text("❌ الرجاء إدخال رقم صحيح.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
        
        elif action == "get_spam_target":
            target_username = text
            spam_details = what_need_to_do_echo.pop(f"{chat_id_str}_spam_details", None)
            count = what_need_to_do_echo.pop(f"{chat_id_str}_spam_count", None)
            
            if not all([spam_details, count]):
                await update.message.reply_text("❌ حدث خطأ ما، يرجى البدء من جديد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
                what_need_to_do_echo[chat_id_str] = ""
                return
            
            what_need_to_do_echo[chat_id_str] = ""
            await update.message.reply_text("🔄 جاري بدء عملية الإرسال...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
            asyncio.create_task(spam_messages(chat_id_str, spam_details, count, target_username))
        
        elif action == "joinchn_getuser":
            chn = text
            what_need_to_do_echo[chat_id_str] = ""
            await update.message.reply_text("⏳ انتظر جاري الانضمام...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
            await joinchn(chat_id_str, chn)
        
        elif action == "leavechn_getuser":
            chn = text
            what_need_to_do_echo[chat_id_str] = ""
            await update.message.reply_text("⏳ انتظر جاري المغادرة...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
            await leave_a_channel(chat_id_str, chn)
        
        elif action == "get_vote_link":
            link = text
            if "t.me" in link and "/" in link:
                what_need_to_do_echo[chat_id_str] = ""
                await update.message.reply_text("✅ تم استلام الرابط. جاري بدء عملية التصويت...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
                asyncio.create_task(boost_post_vote(chat_id_str, link))
            else:
                await update.message.reply_text("❌ الرابط غير صالح. يرجى إرسال رابط منشور تليجرام صحيح.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
        
        elif action == "get_views_link":
            link = text
            if "t.me" in link and "/" in link:
                what_need_to_do_echo[chat_id_str] = ""
                await update.message.reply_text("✅ تم استلام الرابط. جاري بدء عملية زيادة المشاهدات...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
                asyncio.create_task(boost_post_views(chat_id_str, link))
            else:
                await update.message.reply_text("❌ الرابط غير صالح. يرجى إرسال رابط منشور تليجرام صحيح.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
        
        elif action == "get_poll_link":
            link = text
            if "t.me" in link and "/" in link:
                what_need_to_do_echo[f"{chat_id_str}_poll_link"] = link
                what_need_to_do_echo[chat_id_str] = "get_poll_option"
                await update.message.reply_text("✅ تم استلام الرابط. الآن أرسل رقم الخيار الذي تريد التصويت له (مثال: 1):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
            else:
                await update.message.reply_text("❌ الرابط غير صالح. يرجى إرسال رابط منشور تليجرام صحيح.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
        
        elif action == "get_poll_option":
            try:
                option = int(text)
                link = what_need_to_do_echo.pop(f"{chat_id_str}_poll_link", None)
                if link:
                    what_need_to_do_echo[chat_id_str] = ""
                    await update.message.reply_text(f"✅ تم استلام رقم الخيار ({option}). جاري بدء عملية التصويت...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
                    asyncio.create_task(boost_poll_vote(chat_id_str, link, option))
                else:
                    await update.message.reply_text("❌ حدث خطأ ما، لم يتم العثور على الرابط. يرجى المحاولة مرة أخرى.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
            except ValueError:
                await update.message.reply_text("❌ الرجاء إدخال رقم صحيح للخيار.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
        
        elif action == "sleeptime":
            try:
                info["sleeptime"] = int(text)
                save_info()
                await update.message.reply_text("✅ تم الحفظ بنجاح.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
            except ValueError:
                await update.message.reply_text("❌ الرجاء إدخال رقم صحيح.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
            finally:
                what_need_to_do_echo[chat_id_str] = ""
        
        elif action == "deladminecho":
            admin_id_to_del = text
            if admin_id_to_del in info.get("admins", {}):
                del info["admins"][admin_id_to_del]
                save_info()
                stop_all_background_tasks(admin_id_to_del)
                await update.message.reply_text("✅ تم مسح الادمن بنجاح.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
            else:
                await update.message.reply_text("❌ لا يوجد هكذا ادمن.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
            what_need_to_do_echo[chat_id_str] = ""
        
        elif action == "addadminecho":
            admin_id_to_add = text
            if not os.path.isdir(f"echo_ac/{admin_id_to_add}"):
                os.makedirs(f"echo_ac/{admin_id_to_add}")
            info["admins"][admin_id_to_add] = "5"
            save_info()
            await update.message.reply_text("✅ تم اضافه ادمن جديد بنجاح.\n\n- يمكن للادمن اضافه 5 حسابات.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
            what_need_to_do_echo[chat_id_str] = ""
        
        elif action == "add_vip_get_id":
            try:
                vip_id = int(text)
                what_need_to_do_echo[f"{chat_id_str}_vip_id"] = vip_id
                what_need_to_do_echo[chat_id_str] = ""
                keyboard = [
                    [InlineKeyboardButton("⏱️ بالساعات", callback_data="add_vip_hours"), InlineKeyboardButton("📅 بالأيام", callback_data="add_vip_days")],
                    [InlineKeyboardButton("🔙 رجوع", callback_data="manage_vip")]
                ]
                await update.message.reply_text("اختر وحدة الوقت لتفعيل العضوية:", reply_markup=InlineKeyboardMarkup(keyboard))
            except ValueError:
                await update.message.reply_text("❌ الرجاء إدخال ID صحيح (رقم).", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_vip")]]))
        
        elif action == "add_vip_get_duration":
            try:
                duration = int(text)
                vip_id = str(what_need_to_do_echo.pop(f"{chat_id_str}_vip_id"))
                unit = what_need_to_do_echo.pop(f"{chat_id_str}_vip_unit")
                
                if unit == 'hours':
                    delta = timedelta(hours=duration)
                    unit_text = "ساعة"
                else:
                    delta = timedelta(days=duration)
                    unit_text = "يوم"
                
                expiration_time = datetime.now() + delta
                info["vips"][vip_id] = expiration_time.timestamp()
                save_info()
                what_need_to_do_echo[chat_id_str] = ""
                await update.message.reply_text(f"✅ تم تفعيل عضوية VIP للمستخدم {vip_id} لمدة {duration} {unit_text}.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_vip")]]))
            
            except ValueError:
                await update.message.reply_text("❌ الرجاء إدخال مدة صحيحة (رقم).", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_vip")]]))
        
        elif action == "set_trial_duration_get_hours":
            try:
                duration_hours = int(text)
                if duration_hours > 0:
                    info["trial_settings"]["duration_hours"] = duration_hours
                    save_info()
                    what_need_to_do_echo[chat_id_str] = ""
                    await update.message.reply_text(f"✅ تم تحديد مدة الفترة التجريبية إلى {duration_hours} ساعة.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة للوحة التحكم", callback_data="admin_panel_home")]]))
                else:
                    await update.message.reply_text("❌ الرجاء إدخال عدد ساعات أكبر من صفر.")
            except ValueError:
                await update.message.reply_text("❌ الرجاء إدخال رقم صحيح.")
        
        elif action.startswith("setlimt:"):
            admin = action.split(":")[1]
            try:
                limit = int(text)
                info["admins"][admin] = str(limit)
                save_info()
                await update.message.reply_text(f"✅ تم تعيين عدد الحسابات المسموحة للادمن {admin} إلى {limit}!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="myadminsecho")]]))
            except ValueError:
                await update.message.reply_text("❌ الرجاء إدخال رقم صحيح.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="myadminsecho")]]))
            finally:
                what_need_to_do_echo[chat_id_str] = ""

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global what_need_to_do_echo, points_data
    query = update.callback_query
    await query.answer()
    
    if not query.message or query.message.chat.type != "private":
        return
    
    chat_id_str = str(query.message.chat.id)
    
    BotAnalytics.track_event('user_active', chat_id_str)
    
    data = query.data
    
    if not check_access(chat_id_str):
        return
    
    if data == "noop":
        await query.answer(text="⚠️ هذا الزر معطل حالياً لأن هناك عملية تجميع مخصصة قيد التشغيل.", show_alert=True)
        return
    
    if data == "sudohome":
        what_need_to_do_echo[chat_id_str] = ""
        await query.delete_message()
        await start(query, context)
        return
    
    # معالجة أزرار الإذاعة
    if data == "broadcast_menu":
        await broadcast_menu_handler(update, context)
        return
    
    if data == "bot_stats":
        await bot_stats_handler(update, context)
        return
    
    if data == "broadcast_all":
        what_need_to_do_echo[f"{chat_id_str}_broadcast_target"] = "all"
        keyboard = [
            [InlineKeyboardButton("📝 إذاعة نصية", callback_data="broadcast_text")],
            [InlineKeyboardButton("🖼 إذاعة مع صورة", callback_data="broadcast_photo")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="broadcast_menu")]
        ]
        await query.edit_message_text(
            "📢 **إذاعة للجميع**\n\n"
            "اختر نوع الإذاعة:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    if data == "broadcast_admins":
        what_need_to_do_echo[f"{chat_id_str}_broadcast_target"] = "admins"
        keyboard = [
            [InlineKeyboardButton("📝 إذاعة نصية", callback_data="broadcast_text")],
            [InlineKeyboardButton("🖼 إذاعة مع صورة", callback_data="broadcast_photo")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="broadcast_menu")]
        ]
        await query.edit_message_text(
            "📢 **إذاعة للأدمنز**\n\n"
            "اختر نوع الإذاعة:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    if data == "broadcast_vips":
        what_need_to_do_echo[f"{chat_id_str}_broadcast_target"] = "vips"
        keyboard = [
            [InlineKeyboardButton("📝 إذاعة نصية", callback_data="broadcast_text")],
            [InlineKeyboardButton("🖼 إذاعة مع صورة", callback_data="broadcast_photo")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="broadcast_menu")]
        ]
        await query.edit_message_text(
            "📢 **إذاعة للـ VIP**\n\n"
            "اختر نوع الإذاعة:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    if data == "broadcast_text":
        what_need_to_do_echo[chat_id_str] = "broadcast_text_get"
        await query.edit_message_text(
            "📝 أرسل نص الإذاعة الذي تريد إرساله:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="broadcast_menu")]])
        )
        return
    
    if data == "broadcast_photo":
        what_need_to_do_echo[chat_id_str] = "broadcast_photo_get"
        await query.edit_message_text(
            "🖼 أرسل الصورة مع النص (Caption) الذي تريد إرساله:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="broadcast_menu")]])
        )
        return
    
    # أزرار التحكم الجماعي
    if data == "start_all":
        accounts = get_active_accounts(chat_id_str)
        if not accounts:
            await query.edit_message_text("❌ لا توجد حسابات مسجلة.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
            return
        
        await query.edit_message_text("🔄 جاري تشغيل جميع الحسابات...")
        for phone in accounts:
            if phone not in get_running_accounts(chat_id_str):
                # تشغيل مع الإعدادات الافتراضية
                start_background_task(phone, "KekoPointBot", chat_id_str, "انا")
                await asyncio.sleep(0.5)
        
        await query.edit_message_text(f"✅ تم تشغيل {len(accounts)} حساب.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
        return
    
    if data == "stop_all":
        running = get_running_accounts(chat_id_str)
        if not running:
            await query.edit_message_text("ℹ️ لا توجد حسابات قيد التشغيل.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
            return
        
        for phone in running:
            stop_background_task(phone, chat_id_str)
        
        await query.edit_message_text(f"✅ تم إيقاف {len(running)} حساب.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
        return
    
    # زر التجميع المخصص الجديد
    if data == "custom_collect_new":
        what_need_to_do_echo[chat_id_str] = "get_custom_bot"
        await query.edit_message_text(
            "🎯 **تجميع مخصص**\n\n"
            "أرسل يوزر البوت أو رابطه الذي تريد التجميع منه:\n"
            "مثال: @bot_username أو https://t.me/bot_username",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]])
        )
        return
    
    # معالجة أزرار الرابط
    if data == "link_all":
        link = what_need_to_do_echo.get(f"{chat_id_str}_link")
        link_type = await LinkProcessor.detect_link_type(link)
        
        await query.edit_message_text(f"🔄 جاري معالجة الرابط ({link_type})...")
        
        if link_type == 'bot':
            success, message = await LinkProcessor.process_bot_link(chat_id_str, link)
        else:
            success, message = await LinkProcessor.process_channel_link(chat_id_str, link)
        
        what_need_to_do_echo[chat_id_str] = ""
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
        return
    
    if data == "link_running":
        link = what_need_to_do_echo.get(f"{chat_id_str}_link")
        link_type = await LinkProcessor.detect_link_type(link)
        running = get_running_accounts(chat_id_str)
        
        if not running:
            await query.edit_message_text("❌ لا توجد حسابات قيد التشغيل.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
            return
        
        await query.edit_message_text(f"🔄 جاري معالجة الرابط ({link_type}) باستخدام {len(running)} حساب...")
        
        if link_type == 'bot':
            success, message = await LinkProcessor.process_bot_link(chat_id_str, link, running)
        else:
            success, message = await LinkProcessor.process_channel_link(chat_id_str, link, running)
        
        what_need_to_do_echo[chat_id_str] = ""
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
        return
    
    if data == "addecho":
        limit = float('inf')
        if chat_id_str != str(info["sudo"]):
            limit = int(info["admins"].get(chat_id_str, 0))
        
        count = len(get_active_accounts(chat_id_str))
        
        if count < limit:
            what_need_to_do_echo[chat_id_str] = data
            await query.edit_message_text(text="📱 ارسل رقم الحساب الان:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
        else:
            await query.edit_message_text(text="❌ لا يمكنك اضافه المزيد من الحسابات!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
    
    elif data == "leavechn" or data == "templer":
        await query.edit_message_text(text="⏳ حسنا جاري بدأ العملية", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
        accounts = get_active_accounts(chat_id_str)
        for file_stem in accounts:
            client = TelegramClient(f"echo_ac/{chat_id_str}/{file_stem}", API_ID, API_HASH, device_model="iPhone 15 Pro Max", system_version="iOS 17.4")
            try:
                await client.connect()
                if not await client.is_user_authorized():
                    await send_telegram_message(chat_id_str, f"📱 الرقم: {file_stem} غير صالح")
                    continue
                
                if data == "leavechn":
                    dialogs = await client.get_dialogs()
                    count = 0
                    for dialog in dialogs:
                        if dialog.is_channel:
                            await client(LeaveChannelRequest(dialog.entity))
                            count += 1
                    await send_telegram_message(chat_id_str, f"📱 الرقم: {file_stem}\n✅ تم مغادرة {count} قناة")
                
                elif data == "templer":
                    await temp(client)
                    await send_telegram_message(chat_id_str, f"📱 الرقم: {file_stem}\n✅ تم تحويله تمبلر")
            
            except Exception as e:
                print(f"حدث خطأ مع {file_stem}: {e}")
            finally:
                if client.is_connected():
                    await client.disconnect()
            await asyncio.sleep(random.randint(1, 2))
    
    elif data == "leave_7d_collection":
        await query.edit_message_text(text="⏳ حسناً، جاري فحص ومغادرة القنوات التي تم الانضمام إليها قبل 7 أيام أو أكثر...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
        accounts = get_active_accounts(chat_id_str)
        
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        
        for file_stem in accounts:
            client = TelegramClient(f"echo_ac/{chat_id_str}/{file_stem}", API_ID, API_HASH, device_model="iPhone 15 Pro Max", system_version="iOS 17.4")
            try:
                await client.connect()
                if not await client.is_user_authorized():
                    await send_telegram_message(chat_id_str, f"📱 الرقم: {file_stem} غير صالح")
                    continue
                
                dialogs = await client.get_dialogs()
                count = 0
                for dialog in dialogs:
                    if dialog.is_channel:
                        try:
                            participant_info = await client(functions.channels.GetParticipantRequest(channel=dialog.entity, participant='me'))
                            join_date = participant_info.participant.date
                            
                            if join_date < seven_days_ago:
                                await client(LeaveChannelRequest(dialog.entity))
                                count += 1
                                await asyncio.sleep(random.randint(1, 3))
                        except errors.UserNotParticipantError:
                            continue
                        except Exception:
                            continue
                
                await send_telegram_message(chat_id_str, f"📱 الرقم: {file_stem}\n✅ تم مغادرة {count} قناة منضمة منذ أكثر من 7 أيام.")
            
            except Exception as e:
                await send_telegram_message(chat_id_str, f"حدث خطأ عام مع الحساب {file_stem}: {e}")
            finally:
                if client.is_connected():
                    await client.disconnect()
            await asyncio.sleep(random.randint(1, 2))
    
    elif data == "stop_all_collection":
        stop_all_background_tasks(chat_id_str)
        await query.edit_message_text(
            text="✅ تم إرسال طلب إيقاف لجميع عمليات التجميع النشطة.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="sudohome")]])
        )
    
    elif data == "deladminecho":
        what_need_to_do_echo[chat_id_str] = data
        await query.edit_message_text(text="👤 ارسل ايدي الادمن الان:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
    
    elif data == "delall":
        await delall(chat_id_str)
        await query.edit_message_text(text="✅ تم تنفيذ عملية الحذف.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
    
    elif data == "copynum":
        await copynum(chat_id_str)
        await query.edit_message_text(text="✅ تم إرسال نسخ احتياطية.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
    
    elif data == "join_invite_link":
        what_need_to_do_echo[chat_id_str] = "get_link_type"
        await query.edit_message_text(
            text="🔗 أرسل رابط الدعوة أو رابط البوت:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]])
        )
    
    elif data == "joinchn":
        what_need_to_do_echo[chat_id_str] = "joinchn_getuser"
        await query.edit_message_text(text="📢 ارسل يوزر القناة للانضمام اليها:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
    
    elif data == "boost_vote":
        what_need_to_do_echo[chat_id_str] = "get_vote_link"
        await query.edit_message_text(text="👍 أرسل رابط المنشور الذي تريد التصويت عليه:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
    
    elif data == "boost_views":
        what_need_to_do_echo[chat_id_str] = "get_views_link"
        await query.edit_message_text(text="👁️ أرسل رابط المنشور الذي تريد زيادة مشاهداته:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
    
    elif data == "boost_poll":
        what_need_to_do_echo[chat_id_str] = "get_poll_link"
        await query.edit_message_text(text="📊 أرسل رابط منشور الاستفتاء:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
    
    elif data == "spam_message":
        what_need_to_do_echo[chat_id_str] = "get_spam_message"
        await query.edit_message_text(text="💬 الآن، أرسل الرسالة (نص، صورة، ملصق، إلخ) التي تريد تكرارها.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
    
    elif data == "leave_specific_chn":
        what_need_to_do_echo[chat_id_str] = "leavechn_getuser"
        await query.edit_message_text(text="🚪 ارسل يوزر القناة للمغادرة منها:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
    
    elif data == "addadminecho":
        what_need_to_do_echo[chat_id_str] = data
        await query.edit_message_text(text="👑 ارسل ايدي الادمن الان:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
    
    elif data == "sleeptime":
        what_need_to_do_echo[chat_id_str] = data
        await query.edit_message_text(text="⚙️ يرجى إرسال العدد الذي ترغب فيه من الثواني:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
    
    elif data == "admin_panel_home":
        await query.delete_message()
        await admin_panel(query, context)
    
    elif data == "toggle_mode":
        info["bot_mode"] = "free" if info.get("bot_mode") == "paid" else "paid"
        save_info()
        await query.delete_message()
        await admin_panel(query, context)
    
    elif data == "toggle_trial":
        info["trial_settings"]["enabled"] = not info["trial_settings"].get("enabled", False)
        save_info()
        await query.delete_message()
        await admin_panel(query, context)
    
    elif data == "set_trial_duration":
        what_need_to_do_echo[chat_id_str] = "set_trial_duration_get_hours"
        await query.edit_message_text(text="⏱️ أرسل مدة الفترة التجريبية بالساعات:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel_home")]]))
    
    elif data == "manage_vip":
        keyboard = [
            [InlineKeyboardButton("➕ إضافة عضو VIP", callback_data="add_vip")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel_home")]
        ]
        await query.edit_message_text("👑 إدارة العضوية المميزة (VIP):", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "add_vip":
        what_need_to_do_echo[chat_id_str] = "add_vip_get_id"
        await query.edit_message_text("🆔 أرسل ID المستخدم الذي تريد تفعيل عضويته:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_vip")]]))
    
    elif data == "add_vip_hours" or data == "add_vip_days":
        unit = 'hours' if data == 'add_vip_hours' else 'days'
        unit_text = "بالساعات" if unit == 'hours' else "بالأيام"
        what_need_to_do_echo[f"{chat_id_str}_vip_unit"] = unit
        what_need_to_do_echo[chat_id_str] = "add_vip_get_duration"
        await query.edit_message_text(f"⏱️ أرسل مدة التفعيل {unit_text}:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_vip")]]))
    
    elif data == "myadminsecho":
        keyboard = [[InlineKeyboardButton(f"{key}", callback_data=f"setlimt:{key}"), InlineKeyboardButton(str(value), callback_data=f"setlimt:{key}")] for key, value in info.get("admins", {}).items()]
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")])
        await query.edit_message_text("👥 الادمنيه في البوت:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("setlimt:"):
        admin = data.split(":")[1]
        what_need_to_do_echo[chat_id_str] = data
        await query.edit_message_text(f"📊 ارسل عدد الحسابات المسموحة للادمن {admin}:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="myadminsecho")]]))
    
    elif data == "delecho":
        accounts = get_active_accounts(chat_id_str)
        keyboard = [[InlineKeyboardButton(f"📱 {filename}", callback_data=f"del:{filename}"), InlineKeyboardButton("❌", callback_data=f"del:{filename}")] for filename in accounts]
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")])
        await query.edit_message_text("📱 الحسابات الخاصة بك:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "mypoints":
        user_points = points_data.get(chat_id_str, {})
        if not user_points:
            await query.edit_message_text(text="ℹ️ لا توجد بيانات عن النقاط بعد. يرجى بدء التجميع أولاً.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
            return
        
        message_text = "💰 عدد النقاط الحالي لحساباتك:\n\n"
        for phone, points in user_points.items():
            message_text += f"📱 - الحساب `{phone}`: {points} نقطة\n"
        
        await query.edit_message_text(text=message_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]]))
    
    elif data.startswith("del:"):
        filename = data.split(":")[1]
        stop_background_task(filename, chat_id_str)
        session_file = f"echo_ac/{chat_id_str}/{filename}.session"
        if os.path.exists(session_file):
            os.remove(session_file)
            SessionManager.invalidate(chat_id_str)
            await query.edit_message_text(f"✅ تم حذف الرقم: {filename}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="delecho")]]))
        else:
            await query.edit_message_text(f"❌ لا يوجد هكذا رقم: {filename}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="delecho")]]))
    
    elif data == "myecho":
        accounts = get_active_accounts(chat_id_str)
        running_tasks = running_processes.get(chat_id_str, {})
        running_accounts = [k for k in running_tasks.keys() if not k.startswith('custom_')]
        
        custom_task_active = any(key.startswith('custom_') for key in running_tasks)
        
        keyboard = []
        
        if custom_task_active:
            keyboard.append([InlineKeyboardButton("⚠️ جاري تجميع مخصص", callback_data="noop")])
        
        # إضافة أزرار التحكم الجماعي
        if accounts:
            keyboard.append([
                InlineKeyboardButton("▶️ تشغيل الكل", callback_data="start_all"),
                InlineKeyboardButton("⏹️ إيقاف الكل", callback_data="stop_all")
            ])
        
        for filename in accounts:
            if custom_task_active:
                button = InlineKeyboardButton(f"📱 {filename}", callback_data="noop")
                button2 = InlineKeyboardButton("⚙️", callback_data="noop")
            elif filename in running_accounts:
                button = InlineKeyboardButton(f"🟢 {filename}", callback_data=f"stop:{filename}")
                button2 = InlineKeyboardButton("⏹️ إيقاف", callback_data=f"stop:{filename}")
            else:
                button = InlineKeyboardButton(f"🔴 {filename}", callback_data=f"run:{filename}")
                button2 = InlineKeyboardButton("▶️ تشغيل", callback_data=f"run:{filename}")
            keyboard.append([button, button2])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")])
        
        status_text = f"📱 الحسابات الخاصة بك: {len(accounts)}\n🟢 قيد التشغيل: {len(running_accounts)}\n🔴 متوقفة: {len(accounts) - len(running_accounts)}"
        await query.edit_message_text(status_text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("run:"):
        target = data.split(":")[1]
        msg_text = f"⏱️ اختر مدة التجميع للحساب {target}:"
        
        duration_keyboard = [
            [
                InlineKeyboardButton("📅 يوم", callback_data=f"start_collect:{target}:86400"),
                InlineKeyboardButton("📆 أسبوع", callback_data=f"start_collect:{target}:604800"),
                InlineKeyboardButton("📅 شهر", callback_data=f"start_collect:{target}:2592000")
            ],
            [InlineKeyboardButton("🔙 رجوع", callback_data="myecho")]
        ]
        reply_markup = InlineKeyboardMarkup(duration_keyboard)
        await query.edit_message_text(text=msg_text, reply_markup=reply_markup)
    
    elif data.startswith("start_collect:"):
        parts = data.split(":")
        target = parts[1]
        duration = parts[2]
        what_need_to_do_echo[chat_id_str] = f"collect_bot_user:{target}:{duration}"
        await query.edit_message_text(text="🤖 ارسل معرف البوت الذي تريد التجميع منه:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="myecho")]]))
    
    elif data.startswith("stop:"):
        filename = data.split(":")[1]
        stop_background_task(filename, chat_id_str)
        await query.edit_message_text(f"🛑 تم ايقاف عمل الرقم: {filename}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="myecho")]]))
    
    elif data == "custom_collect":
        keyboard = [
            [InlineKeyboardButton("🤖 بوت المهدويون", callback_data="collect_mahdaweon")],
            [InlineKeyboardButton("🤖 بوت دعمكم", callback_data="collect_damkom")],
            [InlineKeyboardButton("🤖 بوت اساسيل", callback_data="collect_asiasell")],
            [InlineKeyboardButton("🤖 بوت المليار", callback_data="collect_billion")],
            [InlineKeyboardButton("🤖 بوت كرستيانو", callback_data="collect_cr7")],
            [InlineKeyboardButton("🤖 بوت الجوكر", callback_data="collect_joker")],
            [InlineKeyboardButton("🎯 تجميع مخصص", callback_data="custom_collect_new")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="sudohome")]
        ]
        await query.edit_message_text("🤖 اختر البوت الذي تريد التجميع منه:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data in ["collect_mahdaweon", "collect_damkom", "collect_asiasell", "collect_billion", "collect_cr7", "collect_joker"]:
        bot_type = ""
        bot_name = ""
        if "mahdaweon" in data:
            bot_type = "mahdaweon"
            bot_name = "المهدويون"
        elif "damkom" in data:
            bot_type = "damkom"
            bot_name = "دعمكم"
        elif "asiasell" in data:
            bot_type = "asiasell"
            bot_name = "اساسيل"
        elif "billion" in data:
            bot_type = "billion"
            bot_name = "المليار"
        elif "cr7" in data:
            bot_type = "cr7"
            bot_name = "كرستيانو"
        elif "joker" in data:
            bot_type = "joker"
            bot_name = "الجوكر"
        
        duration_keyboard = [
            [
                InlineKeyboardButton("📅 يوم", callback_data=f"start_custom_collect:{bot_type}:86400"),
                InlineKeyboardButton("📆 أسبوع", callback_data=f"start_custom_collect:{bot_type}:604800"),
                InlineKeyboardButton("📅 شهر", callback_data=f"start_custom_collect:{bot_type}:2592000")
            ],
            [InlineKeyboardButton("🔙 رجوع", callback_data="custom_collect")]
        ]
        await query.edit_message_text(text=f"⏱️ اختر مدة التجميع من بوت {bot_name}:", reply_markup=InlineKeyboardMarkup(duration_keyboard))
    
    elif data.startswith("start_custom_collect:"):
        parts = data.split(":")
        bot_type = parts[1]
        duration_seconds = parts[2]
        what_need_to_do_echo[chat_id_str] = f"custom_collect_send_to:{bot_type}:{duration_seconds}"
        await query.edit_message_text(
            text="🎯 ارسل ايدي الحساب الذي تريد التجميع له نقاط:\n\n"
                 "- ارسل 'انا' لارسال النقاط لحسابك\n"
                 "- ارسل 'حساب' لارسال النقاط لنفس الحساب",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="custom_collect")]]))

async def temp(client):
    try:
        channel_username = 'Zqqqk'
        channel = await client.get_entity(channel_username)
        posts = await client(GetHistoryRequest(peer=channel, limit=100, offset_date=None, offset_id=0, max_id=0, min_id=0, add_offset=0, hash=0))
        photo_posts = [post for post in posts.messages if post.media and hasattr(post.media, 'photo')]
        if not photo_posts:
            return
        random_photo_post = random.choice(photo_posts)
        photo_path = await client.download_media(random_photo_post.media.photo)
        if not photo_path:
            return
        pfile = await client.upload_file(photo_path)
        await client(UploadProfilePhotoRequest(file=pfile))
        os.remove(photo_path)
        if random_photo_post.message:
            caption_parts = random_photo_post.message.split('\n', 1)
            first_name = caption_parts[0]
            bio = caption_parts[1] if len(caption_parts) > 1 else ""
            await client(UpdateProfileRequest(first_name=first_name, about=bio))
    except Exception as e:
        print(f"Error in temp function: {e}")

# ============ دوال التجميع المخصصة ============
async def run_mahdaweon_collector_for_all_accounts(user_id, send_to):
    accounts = get_active_accounts(user_id)
    
    if not accounts:
        await send_telegram_message(user_id, "❌ لا توجد حسابات قيد التشغيل لبدء التجميع.")
        return
    
    bot_username = '@MHDN313bot'
    await send_telegram_message(user_id, f"🤖 سيتم بدء التجميع من {bot_username} باستخدام {len(accounts)} حساب مفعل.")
    
    for file_stem in accounts:
        try:
            async with TelegramClient(f"echo_ac/{user_id}/{file_stem}", API_ID, API_HASH, device_model="iPhone 15 Pro Max", system_version="iOS 17.4") as client:
                me = await client.get_me()
                if not me:
                    await send_telegram_message(user_id, f"📱 الحساب {file_stem} لا يعمل، جاري التخطي.")
                    continue
                
                my_user_id = me.id
                destination_id = send_to
                if send_to.lower() == "انا":
                    destination_id = user_id
                elif send_to.lower() == "حساب":
                    destination_id = my_user_id
                
                await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n🔄 - بدء التجميع من بوت المهدويون")
                
                channel_entity = await client.get_entity(bot_username)
                await client.send_message(bot_username, f'/start {destination_id}')
                await asyncio.sleep(3)
                
                msg0 = await client.get_messages(bot_username, limit=1)
                await msg0[0].click(2)
                await asyncio.sleep(3)
                
                msg1 = await client.get_messages(bot_username, limit=1)
                await msg1[0].click(0)
                
                for i in range(100):
                    await asyncio.sleep(3)
                    list_hist = await client(GetHistoryRequest(peer=channel_entity, limit=1, offset_date=None, offset_id=0, max_id=0, min_id=0, add_offset=0, hash=0))
                    msgs = list_hist.messages[0]
                    
                    if msgs.message and 'لا يوجد قنوات في الوقت الحالي' in msgs.message:
                        await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n✅ - انتهى التجميع، لا يوجد قنوات.")
                        break
                    
                    if not hasattr(msgs, 'reply_markup') or not msgs.reply_markup:
                        await asyncio.sleep(1)
                        continue
                    
                    try:
                        url = msgs.reply_markup.rows[0].buttons[0].url
                        try:
                            await client(JoinChannelRequest(url))
                        except:
                            bott = url.split('/')[-1]
                            await client(ImportChatInviteRequest(bott))
                        
                        await msgs.click(text='التالي')
                        await asyncio.sleep(3)
                        response_msg = await client.get_messages(bot_username, limit=1)
                        response_text = response_msg[0].message if response_msg else ""
                        points_match = re.search(r'نقاطك الحالية : (\d+)', response_text)
                        points = points_match.group(1) if points_match else "غير معروف"
                        
                        if "تم الاشتراك" in response_text or "حصلت" in response_text:
                            await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n✅ - تم الاشتراك بقناة.\n💰 - النقاط: {points}")
                    
                    except Exception as e:
                        await msgs.click(text='التالي')
                        continue
                
                await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n✅ - تم الانتهاء من التجميع.")
        except asyncio.CancelledError:
            await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n🛑 - تم إيقاف التجميع.")
            break
        except Exception as e:
            await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n❌ - حدث خطأ: {str(e)}")
    
    await send_telegram_message(user_id, "✅ اكتملت عملية التجميع لجميع الحسابات.")

async def run_damkom_collector_for_all_accounts(user_id, send_to):
    accounts = get_active_accounts(user_id)
    
    if not accounts:
        await send_telegram_message(user_id, "❌ لا توجد حسابات قيد التشغيل لبدء التجميع.")
        return
    
    bot_username = '@DamKombot'
    await send_telegram_message(user_id, f"🤖 سيتم بدء التجميع من {bot_username} باستخدام {len(accounts)} حساب مفعل.")
    
    for file_stem in accounts:
        try:
            async with TelegramClient(f"echo_ac/{user_id}/{file_stem}", API_ID, API_HASH, device_model="iPhone 15 Pro Max", system_version="iOS 17.4") as client:
                me = await client.get_me()
                if not me:
                    await send_telegram_message(user_id, f"📱 الحساب {file_stem} لا يعمل، جاري التخطي.")
                    continue
                
                my_user_id = me.id
                destination_id = send_to
                if send_to.lower() == "انا":
                    destination_id = user_id
                elif send_to.lower() == "حساب":
                    destination_id = my_user_id
                
                await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n🔄 - بدء التجميع من بوت دعمكم")
                
                channel_entity = await client.get_entity(bot_username)
                await client.send_message(bot_username, f'/start {destination_id}')
                await asyncio.sleep(3)
                
                msg0 = await client.get_messages(bot_username, limit=1)
                await msg0[0].click(1)
                await asyncio.sleep(3)
                
                msg1 = await client.get_messages(bot_username, limit=1)
                await msg1[0].click(0)
                
                for _ in range(100):
                    await asyncio.sleep(3)
                    list_hist = await client(GetHistoryRequest(peer=channel_entity, limit=1, offset_date=None, offset_id=0, max_id=0, min_id=0, add_offset=0, hash=0))
                    msgs = list_hist.messages[0]
                    
                    if msgs.message and 'لا يوجد قنوات حالياً' in msgs.message:
                        await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n✅ - انتهى التجميع، لا يوجد قنوات.")
                        break
                    
                    try:
                        msg_text = msgs.message
                        if msg_text and "اشترك فالقناة @" in msg_text:
                            channel_to_join = msg_text.split('@')[1].split()[0]
                            entity = await client.get_entity(channel_to_join)
                            if entity:
                                await client(JoinChannelRequest(entity.id))
                                await asyncio.sleep(3)
                                await msgs.click(text='اشتركت ✅')
                                await asyncio.sleep(3)
                                response_msg = await client.get_messages(bot_username, limit=1)
                                response_text = response_msg[0].message if response_msg else ""
                                points_match = re.search(r'عدد نقاطك : (\d+)', response_text)
                                points = points_match.group(1) if points_match else "غير معروف"
                                
                                await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n✅ - تم الاشتراك بقناة.\n💰 - النقاط: {points}")
                    except Exception as e:
                        continue
                
                await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n✅ - تم الانتهاء من التجميع.")
        except asyncio.CancelledError:
            await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n🛑 - تم إيقاف التجميع.")
            break
        except Exception as e:
            await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n❌ - حدث خطأ: {str(e)}")
    
    await send_telegram_message(user_id, "✅ اكتملت عملية التجميع لجميع الحسابات.")

async def run_asiasell_collector_for_all_accounts(user_id, send_to):
    accounts = get_active_accounts(user_id)
    
    if not accounts:
        await send_telegram_message(user_id, "❌ لا توجد حسابات قيد التشغيل لبدء التجميع.")
        return
    
    bot_username = '@yynnurybot'
    await send_telegram_message(user_id, f"🤖 سيتم بدء التجميع من {bot_username} باستخدام {len(accounts)} حساب.")
    
    for file_stem in accounts:
        try:
            async with TelegramClient(f"echo_ac/{user_id}/{file_stem}", API_ID, API_HASH, device_model="iPhone 15 Pro Max", system_version="iOS 17.4") as client:
                me = await client.get_me()
                if not me:
                    await send_telegram_message(user_id, f"📱 الحساب {file_stem} لا يعمل، جاري التخطي.")
                    continue
                
                my_user_id = me.id
                destination_id = send_to
                if send_to.lower() == "انا":
                    destination_id = user_id
                elif send_to.lower() == "حساب":
                    destination_id = my_user_id
                
                await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n🔄 - بدء التجميع من بوت اساسيل")
                
                channel_entity = await client.get_entity(bot_username)
                await client.send_message(bot_username, f'/start {destination_id}')
                await asyncio.sleep(3)
                
                msg0 = await client.get_messages(bot_username, limit=1)
                await msg0[0].click(2)
                await asyncio.sleep(3)
                
                msg1 = await client.get_messages(bot_username, limit=1)
                await msg1[0].click(0)
                
                chs = 1
                for i in range(100):
                    await asyncio.sleep(3)
                    list_hist = await client(GetHistoryRequest(peer=channel_entity, limit=1, offset_date=None, offset_id=0, max_id=0, min_id=0, add_offset=0, hash=0))
                    msgs = list_hist.messages[0]
                    
                    if msgs.message and 'لا يوجد قنوات في الوقت الحالي , قم بتجميع النقاط بطريقة مختلفة' in msgs.message:
                        await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n✅ - تم الانتهاء من التجميع.")
                        break
                    
                    if not hasattr(msgs, 'reply_markup') or not msgs.reply_markup or not msgs.reply_markup.rows[0].buttons:
                        continue
                    
                    url = msgs.reply_markup.rows[0].buttons[0].url
                    try:
                        try:
                            await client(JoinChannelRequest(url))
                        except:
                            bott = url.split('/')[-1]
                            await client(ImportChatInviteRequest(bott))
                        
                        msg2 = await client.get_messages(bot_username, limit=1)
                        await msg2[0].click(text='تحقق')
                        chs += 1
                        await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n✅ - تم الانضمام في {chs} قناة.")
                    except:
                        msg2 = await client.get_messages(bot_username, limit=1)
                        await msg2[0].click(text='التالي')
                        chs += 1
                
                await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n✅ - تم الانتهاء من التجميع.")
        
        except asyncio.CancelledError:
            await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n🛑 - تم إيقاف التجميع.")
            break
        except Exception as e:
            await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n❌ - حدث خطأ فادح: {str(e)}")
    
    await send_telegram_message(user_id, "✅ اكتملت عملية التجميع لجميع الحسابات.")

async def run_billion_collector_for_all_accounts(user_id, send_to):
    accounts = get_active_accounts(user_id)
    if not accounts:
        await send_telegram_message(user_id, "❌ لا توجد حسابات لبدء التجميع.")
        return
    
    bot_username = '@EEObot'
    await send_telegram_message(user_id, f"🤖 سيتم بدء التجميع من {bot_username} باستخدام {len(accounts)} حساب.")
    
    for file_stem in accounts:
        try:
            async with TelegramClient(f"echo_ac/{user_id}/{file_stem}", API_ID, API_HASH, device_model="iPhone 15 Pro Max", system_version="iOS 17.4") as client:
                me = await client.get_me()
                if not me:
                    await send_telegram_message(user_id, f"📱 الحساب {file_stem} لا يعمل، جاري التخطي.")
                    continue
                
                my_user_id = me.id
                destination_id = send_to
                if send_to.lower() == "انا":
                    destination_id = user_id
                elif send_to.lower() == "حساب":
                    destination_id = my_user_id
                
                channel_entity = await client.get_entity(bot_username)
                await client.send_message(bot_username, f'/start {destination_id}')
                await asyncio.sleep(3)
                msg0 = await client.get_messages(bot_username, limit=1)
                await msg0[0].click(2)
                await asyncio.sleep(3)
                msg1 = await client.get_messages(bot_username, limit=1)
                await msg1[0].click(0)
                chs = 1
                for i in range(100):
                    await asyncio.sleep(3)
                    list_hist = await client(GetHistoryRequest(peer=channel_entity, limit=1, offset_date=None, offset_id=0, max_id=0, min_id=0, add_offset=0, hash=0))
                    msgs = list_hist.messages[0]
                    if msgs.message.find('لا يوجد قنوات في الوقت الحالي , قم بتجميع النقاط بطريقة مختلفة') != -1:
                        await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n✅ - انتهى التجميع، لا يوجد قنوات.")
                        break
                    
                    if not hasattr(msgs, 'reply_markup') or not msgs.reply_markup:
                        await asyncio.sleep(1)
                        continue
                    
                    url = msgs.reply_markup.rows[0].buttons[0].url
                    try:
                        try:
                            await client(JoinChannelRequest(url))
                        except:
                            bott = url.split('/')[-1]
                            await client(ImportChatInviteRequest(bott))
                        
                        msg2 = await client.get_messages(bot_username, limit=1)
                        await msg2[0].click(text='تحقق')
                        chs += 1
                        await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n✅ - تم الانضمام في {chs} قناة.")
                    except:
                        msg2 = await client.get_messages(bot_username, limit=1)
                        await msg2[0].click(text='التالي')
                        chs += 1
                
                await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n✅ - تم الانتهاء من التجميع.")
        
        except asyncio.CancelledError:
            await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n🛑 - تم إيقاف التجميع.")
            break
        except Exception as e:
            await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n❌ - حدث خطأ فادح: {str(e)}")
    
    await send_telegram_message(user_id, "✅ اكتملت عملية التجميع لجميع الحسابات.")

async def run_cr7_collector_for_all_accounts(user_id, send_to):
    accounts = get_active_accounts(user_id)
    
    if not accounts:
        await send_telegram_message(user_id, "❌ لا توجد حسابات قيد التشغيل لبدء التجميع.")
        return
    
    bot_username = '@PPAHSBOT'
    await send_telegram_message(user_id, f"🤖 سيتم بدء التجميع من {bot_username} باستخدام {len(accounts)} حساب.")
    
    for file_stem in accounts:
        try:
            async with TelegramClient(f"echo_ac/{user_id}/{file_stem}", API_ID, API_HASH, device_model="iPhone 15 Pro Max", system_version="iOS 17.4") as client:
                me = await client.get_me()
                if not me:
                    await send_telegram_message(user_id, f"📱 الحساب {file_stem} لا يعمل، جاري التخطي.")
                    continue
                
                my_user_id = me.id
                destination_id = send_to
                if send_to.lower() == "انا":
                    destination_id = user_id
                elif send_to.lower() == "حساب":
                    destination_id = my_user_id
                
                await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n🔄 - بدء التجميع من بوت كرستيانو")
                
                channel_entity = await client.get_entity(bot_username)
                await client.send_message(bot_username, f'/start {destination_id}')
                await asyncio.sleep(3)
                
                msg0 = await client.get_messages(bot_username, limit=1)
                await msg0[0].click(2)
                await asyncio.sleep(3)
                
                msg1 = await client.get_messages(bot_username, limit=1)
                await msg1[0].click(0)
                
                chs = 1
                for i in range(100):
                    await asyncio.sleep(3)
                    list_hist = await client(GetHistoryRequest(peer=channel_entity, limit=1, offset_date=None, offset_id=0, max_id=0, min_id=0, add_offset=0, hash=0))
                    msgs = list_hist.messages[0]
                    
                    if msgs.message and 'لا يوجد قنوات في الوقت الحالي , قم بتجميع النقاط بطريقة مختلفة' in msgs.message:
                        await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n✅ - انتهى التجميع، لا يوجد قنوات.")
                        break
                    
                    if not hasattr(msgs, 'reply_markup') or not msgs.reply_markup:
                        await asyncio.sleep(1)
                        continue
                    
                    url = msgs.reply_markup.rows[0].buttons[0].url
                    try:
                        try:
                            await client(JoinChannelRequest(url))
                        except:
                            bott = url.split('/')[-1]
                            await client(ImportChatInviteRequest(bott))
                        
                        msg2 = await client.get_messages(bot_username, limit=1)
                        await msg2[0].click(text='تحقق')
                        chs += 1
                        await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n✅ - تم الانضمام في {chs} قناة.")
                    except:
                        msg2 = await client.get_messages(bot_username, limit=1)
                        await msg2[0].click(text='التالي')
                        chs += 1
                
                await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n✅ - تم الانتهاء من التجميع.")
        except asyncio.CancelledError:
            await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n🛑 - تم إيقاف التجميع.")
            break
        except Exception as e:
            await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n❌ - حدث خطأ فادح: {str(e)}")
    
    await send_telegram_message(user_id, "✅ اكتملت عملية التجميع لجميع الحسابات.")

async def run_joker_collector_for_all_accounts(user_id, send_to):
    accounts = get_active_accounts(user_id)
    
    if not accounts:
        await send_telegram_message(user_id, "❌ لا توجد حسابات قيد التشغيل لبدء التجميع.")
        return
    
    bot_username = '@A_MAN9300BOT'
    await send_telegram_message(user_id, f"🤖 سيتم بدء التجميع من {bot_username} باستخدام {len(accounts)} حساب.")
    
    for file_stem in accounts:
        try:
            async with TelegramClient(f"echo_ac/{user_id}/{file_stem}", API_ID, API_HASH, device_model="iPhone 15 Pro Max", system_version="iOS 17.4") as client:
                me = await client.get_me()
                if not me:
                    await send_telegram_message(user_id, f"📱 الحساب {file_stem} لا يعمل، جاري التخطي.")
                    continue
                
                my_user_id = me.id
                destination_id = send_to
                if send_to.lower() == "انا":
                    destination_id = user_id
                elif send_to.lower() == "حساب":
                    destination_id = my_user_id
                
                await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n🔄 - بدء التجميع من بوت الجوكر")
                
                channel_entity = await client.get_entity(bot_username)
                await client.send_message(bot_username, f'/start {destination_id}')
                await asyncio.sleep(3)
                
                msg0 = await client.get_messages(bot_username, limit=1)
                await msg0[0].click(2)
                await asyncio.sleep(3)
                
                msg1 = await client.get_messages(bot_username, limit=1)
                await msg1[0].click(0)
                
                chs = 1
                for i in range(100):
                    await asyncio.sleep(3)
                    list_hist = await client(GetHistoryRequest(peer=channel_entity, limit=1, offset_date=None, offset_id=0, max_id=0, min_id=0, add_offset=0, hash=0))
                    msgs = list_hist.messages[0]
                    
                    if msgs.message and 'لا يوجد قنوات في الوقت الحالي , قم بتجميع النقاط بطريقة مختلفة' in msgs.message:
                        await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n✅ - انتهى التجميع، لا يوجد قنوات.")
                        break
                    
                    if not hasattr(msgs, 'reply_markup') or not msgs.reply_markup:
                        await asyncio.sleep(1)
                        continue
                    
                    url = msgs.reply_markup.rows[0].buttons[0].url
                    try:
                        try:
                            await client(JoinChannelRequest(url))
                        except:
                            bott = url.split('/')[-1]
                            await client(ImportChatInviteRequest(bott))
                        
                        msg2 = await client.get_messages(bot_username, limit=1)
                        await msg2[0].click(text='تحقق')
                        chs += 1
                        await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n✅ - تم الانضمام في {chs} قناة.")
                    except:
                        msg2 = await client.get_messages(bot_username, limit=1)
                        await msg2[0].click(text='التالي')
                        chs += 1
                
                await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n✅ - تم الانتهاء من التجميع.")
        except asyncio.CancelledError:
            await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n🛑 - تم إيقاف التجميع.")
            break
        except Exception as e:
            await send_telegram_message(user_id, f"📱 الحساب: {file_stem}\n❌ - حدث خطأ فادح: {str(e)}")
    
    await send_telegram_message(user_id, "✅ اكتملت عملية التجميع لجميع الحسابات.")

def main() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def start_notifier():
        await notifier.start()
    
    loop.run_until_complete(start_notifier())
    
    application = Application.builder().token(bot_token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echoMaker))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND & ~filters.TEXT, echoMaker))
    application.add_handler(CallbackQueryHandler(button))
    
    print("✅ Bot started with all enhancements!")
    print("🚀 Connection pool enabled")
    print("📢 Broadcast system enabled")
    print("📈 Analytics system enabled")
    print("🔗 Smart link processor enabled")
    print("🎯 Custom collector enabled")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

@atexit.register
def cleanup():
    print("🔄 Cleaning up resources...")
    thread_pool.shutdown(wait=False)
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(ConnectionPool.cleanup())
        loop.run_until_complete(keko_api.close())
        loop.run_until_complete(notifier.stop())
    except:
        pass
    print("✅ Cleanup completed!")

if __name__ == "__main__":
    main()
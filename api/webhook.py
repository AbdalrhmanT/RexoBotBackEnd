from http.server import BaseHTTPRequestHandler
import os
import json
import asyncio
import requests
import datetime
from telebot.async_telebot import AsyncTeleBot
import firebase_admin
from firebase_admin import credentials, firestore, storage
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telebot import types

# Initialize bot
BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = AsyncTeleBot(BOT_TOKEN)

# Initialize Firebase
firebase_config = json.loads(os.environ.get('FIREBASE_SERVICE_ACCOUNT'))
cred = credentials.Certificate(firebase_config)
firebase_admin.initialize_app(cred, {'storageBucket': "telegrambot1-2d42b.appspot.com"})
db = firestore.client()
bucket = storage.bucket()

def generate_start_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Open Rex App", web_app=WebAppInfo(url="https://moneyclaim.xyz")))
    return keyboard

@bot.message_handler(commands=['start'])
async def start(message):
    user_id = str(message.from_user.id)
    user_first_name = str(message.from_user.first_name)
    user_last_name = message.from_user.last_name
    user_username = message.from_user.username
    user_language_code = str(message.from_user.language_code)
    is_premium = getattr(message.from_user, 'is_premium', False)  # Handle cases where 'is_premium' might not exist
    text = message.text.split()
    welcome_message = (
        f"Hi, {user_first_name}! \n\n"
        f"Welcome to RexCoin! \n\n"
        f"Here You Can earn $Coins by Mining Them!!! \n\n"
        f"Invite friends And Watch Ads Its Important! \n\n"
        f"Lets Play Now !!! \n\n"
    )

    try:
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()

        user_image = None
        if not user_doc.exists:
            photos = await bot.get_user_profile_photos(user_id, limit=1)
            if photos.total_count > 0:
                file_id = photos.photos[0][-1].file_id
                file_info = await bot.get_file(file_id)
                file_path = file_info.file_path
                file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

                # Download the image
                response = requests.get(file_url)
                if response.status_code == 200:
                    # Upload to Firebase Storage
                    blob = bucket.blob(f"user_images/{user_id}.jpg")
                    blob.upload_from_string(response.content, content_type='image/jpeg')

                    # Generate the correct URL
                    user_image = blob.generate_signed_url(datetime.timedelta(days=365), method='GET')

        user_data = {
            'userImage': user_image,
            'firstName': user_first_name,
            'lastName': user_last_name,
            'username': user_username,
            'languageCode': user_language_code,
            'isPremium': is_premium,
            'referrals': {},
            'balance': 0,
            'mineRate': 0.001,
            'isMining': False,
            'miningStartedTime': None,
            'daily': {
                'claimedTime': None,
                'claimedDay': 0,
            },
            'links': None,
        }

        if len(text) > 1 and text[1].startswith('ref_'):
            referrer_id = text[1][4:]
            referrer_ref = db.collection('users').document(referrer_id)
            referrer_doc = referrer_ref.get()

            if referrer_doc.exists:
                user_data['referredBy'] = referrer_id

                referrer_data = referrer_doc.to_dict()
                bonus_amount = 10000 if is_premium else 5000

                referrals = referrer_data.get('referrals', {})
                referrals[user_id] = {
                    'addedValue': bonus_amount,
                    'firstName': user_first_name,
                    'lastName': user_last_name,
                    'userImage': user_image,
                }
                new_balance = referrer_data.get('balance', 0) + bonus_amount

                referrer_ref.update({
                    'balance': new_balance,
                    'referrals': referrals,
                })

                # Notify referrer about the bonus
                try:
                    notification_message = (
                        f"🎉 Congratulations! You received a referral bonus of {bonus_amount} coins 🎉\n\n"
                        f"Referral Info:\n"
                        f"👤 {user_first_name} {user_last_name if user_last_name else ''}\n"
                        f"💰 Your new balance: {new_balance} coins\n"
                    )
                    await bot.send_message(referrer_id, notification_message)
                except Exception as e:
                    print(f"Failed to send notification to referrer {referrer_id}: {str(e)}")
            else:
                user_data['referredBy'] = None
        else:
            user_data['referredBy'] = None

        user_ref.set(user_data)

        keyboard = generate_start_keyboard()
        await bot.reply_to(message, welcome_message, reply_markup=keyboard)

    except Exception as e:
        error_message = "Error. Please Try Again!"
        await bot.reply_to(message, error_message)
        print(f"Error: {str(e)}")

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # قراءة بيانات الطلب
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        update_dict = json.loads(post_data.decode('utf-8'))
        
        # تشغيل المهمة غير المتزامنة لمعالجة التحديث
        asyncio.run(self.process_update(update_dict))
        
        # إرسال استجابة HTTP 200
        self.send_response(200)
        self.end_headers()

    async def process_update(self, update_dict):
        # معالجة التحديث باستخدام TeleBot
        update = types.Update.de_json(update_dict)
        await bot.process_new_updates([update])

    def do_GET(self):
        # استجابة بسيطة لفحص حالة البوت
        self.send_response(200)
        self.end_headers()
        self.wfile.write("Bot is running".encode())

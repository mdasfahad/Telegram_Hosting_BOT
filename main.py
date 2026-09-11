import os
import sys
import time
import subprocess
import telebot
from telebot import types

# ================= সেটআপ ও কনফিগারেশন =================
API_TOKEN = '8483362473:AAFqMixrkiuGnwozELnBZyl9-neGmY6y4UI'          # @BotFather থেকে পাওয়া টোকেন দিন
ADMIN_ID = 8289191009                       # আপনার টেলিগ্রাম আইডি
FORCE_CHANNEL = "@FreeIncome_TechBD"              # চ্যানেল ইউজারনেম (@FreeIncome_TechBD)
SUPPORT_USERNAME = "YourSupportUsername"    # আপনার সাপোর্ট ইউজারনেম (sabbir2850

bot = telebot.TeleBot(API_TOKEN)

# ================= ডাটাবেজ ও ফোল্ডার সেটআপ =================
users_db = {}  # {user_id: {"approved": True/False, "plan": "Standard"}}
payment_numbers = {
    "bkash": "01700000000", 
    "nagad": "01800000000",
    "rocket": "01900000000"
}
# মার্চেন্ট বা অটো পেমেন্ট API কনফিগারেশন (যেমন: Rupantor Pay)
MERCHANT_CONFIG = {
    "api_key": "YOUR_MERCHANT_API_KEY",
    "payment_url": "https://rupantorpay.com/api/create-checkout" # আপনার মার্চেন্ট ইউআরএল
}

active_processes = {}
user_states = {}

HOST_DIR = "./hosted_bots"
os.makedirs(HOST_DIR, exist_ok=True)

# ================= হেলপার ফাংশন =================
def check_force_sub(user_id):
    if not FORCE_CHANNEL or FORCE_CHANNEL == "@yourchannel":
        return True
    try:
        member = bot.get_chat_member(FORCE_CHANNEL, user_id)
        return member.status in ['creator', 'administrator', 'member']
    except Exception:
        return True

# ১. স্ক্রিনের নিচের স্থায়ী কিবোর্ড মেনু (সবসময় থাকবে)
def get_main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("🛒 Buy Plan")
    btn2 = types.KeyboardButton("🚀 Host My Bot")
    btn3 = types.KeyboardButton("💬 Support")
    btn4 = types.KeyboardButton("ℹ️ FAQ")
    
    markup.add(btn1, btn2)
    markup.add(btn3, btn4)
    
    # শুধুমাত্র এডমিনের জন্য এডমিন প্যানেল বাটন
    if user_id == ADMIN_ID:
        markup.add(types.KeyboardButton("🔐 Admin Panel"))
        
    return markup

# ================= /start কমান্ড =================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    if user_id not in users_db:
        users_db[user_id] = {"approved": False, "plan": None}

    # ফোর্স সাবস্ক্রিপশন চেক
    if not check_force_sub(user_id):
        markup = types.InlineKeyboardMarkup()
        btn_channel = types.InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{FORCE_CHANNEL.replace('@','')}")
        markup.add(btn_channel)
        bot.send_message(
            message.chat.id, 
            f"⚠️ **বটটি ব্যবহার করতে আমাদের চ্যানেলে জয়েন করুন!**\n\nচ্যানেল: {FORCE_CHANNEL}", 
            parse_mode="Markdown", 
            reply_markup=markup
        )
        return

    bot.send_message(
        message.chat.id, 
        "👋 **স্বাগতম আমাদের Bot Hosting Engine এ!**\n\nনিচের মেনু থেকে আপনার পছন্দ অনুযায়ী অপশন বেছে নিন:", 
        parse_mode="Markdown", 
        reply_markup=get_main_keyboard(user_id)
    )

# ================= টেক্সট ও মেনু বাটন হ্যান্ডলার =================
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    text = message.text

    # ১. Buy Plan অপশন (অটো পেমেন্ট ও ম্যানুয়াল পেমেন্ট)
    if text == "🛒 Buy Plan":
        markup = types.InlineKeyboardMarkup(row_width=1)
        # অটো পেমেন্ট মার্চেন্ট লিঙ্ক (যেমন রূপান্তর পে)
        merchant_pay_url = f"https://t.me/{bot.get_me().username}?start=autopay_{user_id}" 
        btn_auto = types.InlineKeyboardButton("💳 Auto Pay (Bkash/Nagad/Rocket)", url=f"https://pay.yourdomain.com/checkout?user_id={user_id}&amount=100")
        btn_manual = types.InlineKeyboardButton("📱 Manual Send Money", callback_data="manual_pay")
        markup.add(btn_auto, btn_manual)
        
        bot.send_message(
            message.chat.id, 
            "📜 **হোস্টিং প্ল্যান নির্বাচন করুন:**\n\n🔹 **Standard Host:** 100 BDT / Month\n\nনিচের যেকোনো একটি পেমেন্ট পদ্ধতি বেছে নিন:", 
            parse_mode="Markdown", 
            reply_markup=markup
        )
        return

    # ২. Host My Bot অপশন
    elif text == "🚀 Host My Bot":
        if not users_db.get(user_id, {}).get("approved", False):
            bot.send_message(message.chat.id, "❌ **আপনার হোস্টিং এক্সেস নেই!**\n\nবট হোস্ট করতে প্রথমে '🛒 Buy Plan' থেকে প্ল্যান কিনুন।", parse_mode="Markdown")
            return
        
        bot.send_message(
            message.chat.id, 
            "📂 **আপনার পাইথন ফাইল (`.py`) টি আপলোড করুন:**\n\n*(ফাইলটি আপলোড করার পর সিস্টেম অটো চেক করবে এবং প্রসেস রান করাবে)*", 
            parse_mode="Markdown"
        )
        user_states[user_id] = "waiting_for_bot_file"
        return

    # ৩. Support (সরাসরি এডমিন ইনবক্স উইথ অটোমেটিক মেসেজ)
    elif text == "💬 Support":
        encoded_text = "Hello%20Admin,%20I%20need%20help%20regarding%20bot%20hosting."
        direct_inbox_url = f"https://t.me/{SUPPORT_USERNAME.replace('@','')}?text={encoded_text}"
        
        markup = types.InlineKeyboardMarkup()
        btn_inbox = types.InlineKeyboardButton("📩 Direct Chat with Admin", url=direct_inbox_url)
        markup.add(btn_inbox)
        
        bot.send_message(
            message.chat.id, 
            "💬 **সাপোর্ট সেন্টার:**\n\nযেকোনো সাহায্যের জন্য নিচের বাটনে ক্লিক করুন। সরাসরি এডমিন ইনবক্সে অটো-টাইপ করা মেসেজ সহ নিয়ে যাবে।", 
            parse_mode="Markdown", 
            reply_markup=markup
        )
        return

    # ৪. FAQ
    elif text == "ℹ️ FAQ":
        faq_text = (
            "ℹ️ **সাধারণ জিজ্ঞাসাসমূহ (FAQ):**\n\n"
            "❓ **১. কীভাবে বট হোস্ট করবেন?**\n"
            "👉 '🛒 Buy Plan' থেকে পেমেন্ট কমপ্লিট করুন। এপ্রুভ হলে '🚀 Host My Bot' অপশনে আপনার `.py` ফাইল পাঠালে সাথে সাথেই লাইভ হয়ে যাবে।\n\n"
            "❓ **২. অটো পেমেন্ট কীভাবে কাজ করে?**\n"
            "👉 'Auto Pay' তে ক্লিক করে বিকাশ, নগদ বা রকেটের মাধ্যমে ইনস্ট্যান্ট পেমেন্ট করে এক্সেস অটোমেটিক একটিভ করতে পারবেন।\n\n"
            "❓ **৩. ফাইল আপডেট করতে চাইলে?**\n"
            "👉 নতুন ফাইল আপলোড করলে আগের বট অটো স্টপ হয়ে নতুন ফাইল চালু হবে।"
        )
        bot.send_message(message.chat.id, faq_text, parse_mode="Markdown")
        return

    # ৫. Admin Panel (শুধুমাত্র এডমিনের জন্য)
    elif text == "🔐 Admin Panel":
        if user_id != ADMIN_ID:
            bot.send_message(message.chat.id, "❌ আপনার এই প্যানেলে এক্সেস নেই!")
            return
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("➕ Add User Access", callback_data="admin_add_u"),
            types.InlineKeyboardButton("➖ Remove Access", callback_data="admin_rem_u"),
            types.InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast"),
            types.InlineKeyboardButton("📱 Payment Numbers", callback_data="admin_numbers")
        )
        bot.send_message(message.chat.id, "🛠️ **এডমিন কন্ট্রোল প্যানেল:**", parse_mode="Markdown", reply_markup=markup)
        return

    # ================= এডমিন স্টেট হ্যান্ডলিং =================
    state = user_states.get(user_id)

    if state == "waiting_for_trx":
        trx_id = text.strip()
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Approve", callback_data=f"app_{user_id}_Standard"),
            types.InlineKeyboardButton("❌ Reject", callback_data=f"rej_{user_id}")
        )
        bot.send_message(ADMIN_ID, f"📥 **নতুন ম্যানুয়াল পেমেন্ট রিকোয়েস্ট!**\n👤 User ID: `{user_id}`\n🧾 TrxID: `{trx_id}`", parse_mode="Markdown", reply_markup=markup)
        bot.reply_to(message, "✅ আপনার পেমেন্ট ট্রানজেকশন আইডি জমা দেওয়া হয়েছে! এডমিন ভেরিফাই করে এপ্রুভ করে দেবে।")
        user_states[user_id] = None

    elif state == "waiting_for_manual_user_add":
        try:
            target_id = int(text.strip())
            users_db[target_id] = {"approved": True, "plan": "Admin Granted"}
            bot.reply_to(message, f"✅ User ID `{target_id}` কে হোস্টিং এক্সেস দেওয়া হয়েছে!", parse_mode="Markdown")
        except Exception:
            bot.reply_to(message, "❌ সঠিক Numeric User ID দিন!")
        user_states[user_id] = None

    elif state == "waiting_for_manual_user_rem":
        try:
            target_id = int(text.strip())
            if target_id in users_db:
                users_db[target_id]["approved"] = False
                if target_id in active_processes:
                    try:
                        active_processes[target_id].terminate()
                    except Exception:
                        pass
                bot.reply_to(message, f"✅ User ID `{target_id}` এর এক্সেস ও রানিং বট বন্ধ করা হয়েছে!", parse_mode="Markdown")
            else:
                bot.reply_to(message, "❌ এই আইডি পাওয়া যায়নি!")
        except Exception:
            bot.reply_to(message, "❌ সঠিক Numeric User ID দিন!")
        user_states[user_id] = None

    elif state == "waiting_for_broadcast":
        count = 0
        for uid in list(users_db.keys()):
            try:
                bot.send_message(uid, f"📢 **Announcement:**\n\n{text}", parse_mode="Markdown")
                count += 1
            except Exception:
                pass
        bot.reply_to(message, f"✅ ব্রডকাস্ট সম্পন্ন হয়েছে! মোট **{count}** জন ইউজার বার্তা পেয়েছেন।", parse_mode="Markdown")
        user_states[user_id] = None

    elif state == "waiting_for_add_number":
        try:
            method, num = text.strip().split(":")
            payment_numbers[method.lower()] = num
            bot.reply_to(message, f"✅ **{method.upper()}** নাম্বার আপডেট হয়েছে: `{num}`", parse_mode="Markdown")
        except Exception:
            bot.reply_to(message, "❌ ভুল ফরম্যাট! উদাহরণ: `bkash:01711223344`")
        user_states[user_id] = None

# ================= ইনলাইন কলব্যাক হ্যান্ডলার =================
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    user_id = call.from_user.id

    if call.data == "manual_pay":
        pay_numbers_txt = "\n".join([f"📱 **{k.upper()}:** `{v}`" for k, v in payment_numbers.items()])
        pay_msg = f"💳 **ম্যানুয়াল পেমেন্ট নির্দেশিকা:**\n\nনিচের নাম্বারে সেন্ড মানি করুন:\n{pay_numbers_txt}\n\nটাকা পাঠানোর পর আপনার **TrxID (ট্রানজেকশন আইডি)** লিখে মেসেজ পাঠান:"
        bot.send_message(call.message.chat.id, pay_msg, parse_mode="Markdown")
        user_states[user_id] = "waiting_for_trx"

    elif call.data == "admin_add_u":
        bot.send_message(call.message.chat.id, "➕ এক্সেস দিতে ইউজারের **Telegram Numeric ID** লিখুন:")
        user_states[user_id] = "waiting_for_manual_user_add"

    elif call.data == "admin_rem_u":
        bot.send_message(call.message.chat.id, "➖ এক্সেস সরাতে ইউজারের **Telegram Numeric ID** লিখুন:")
        user_states[user_id] = "waiting_for_manual_user_rem"

    elif call.data == "admin_broadcast":
        bot.send_message(call.message.chat.id, "📢 সব ইউজারের উদ্দেশ্যে পাঠানোর বার্তাটি (Broadcast Message) লিখুন:")
        user_states[user_id] = "waiting_for_broadcast"

    elif call.data == "admin_numbers":
        msg = "📱 **বর্তমান পেমেন্ট নাম্বারসমূহ:**\n\n"
        for k, v in payment_numbers.items():
            msg += f"• **{k.upper()}:** `{v}`\n"
        msg += "\nনতুন নাম্বার দিতে লিখুন: `method:number`\n(যেমন: `bkash:01711223344`):"
        bot.send_message(call.message.chat.id, msg, parse_mode="Markdown")
        user_states[user_id] = "waiting_for_add_number"

    elif call.data.startswith("app_"):
        _, target_id, p_name = call.data.split("_")
        users_db[int(target_id)] = {"approved": True, "plan": p_name}
        try:
            bot.send_message(int(target_id), "🎉 **অভিনন্দন!** আপনার পেমেন্ট এপ্রুভ করা হয়েছে। এখন '🚀 Host My Bot' বাটনে চেপে ফাইল আপলোড করতে পারেন।")
        except Exception:
            pass
        bot.edit_message_text(call.message.text + "\n\n✅ **APPROVED**", call.message.chat.id, call.message.message_id)

    elif call.data.startswith("rej_"):
        target_id = call.data.split("_")[1]
        try:
            bot.send_message(int(target_id), "❌ **আপনার পেমেন্ট তথ্য ভুল থাকায় রিজেক্ট করা হয়েছে।**")
        except Exception:
            pass
        bot.edit_message_text(call.message.text + "\n\n❌ **REJECTED**", call.message.chat.id, call.message.message_id)

# ================= ফাইল রিসিভ ও ব্যাকগ্রাউন্ড রান =================
@bot.message_handler(content_types=['document'])
def handle_document(message):
    user_id = message.from_user.id
    state = user_states.get(user_id)

    if state == "waiting_for_bot_file":
        if not message.document.file_name.endswith('.py'):
            bot.reply_to(message, "❌ ভুল ফাইল! শুধুমাত্র পাইথন ফাইল (`.py`) আপলোড করুন।")
            return
        
        status_msg = bot.reply_to(message, "⏳ **আপনার ফাইল সেভ ও প্রসেস করা হচ্ছে...**", parse_mode="Markdown")

        # ফাইল ডাউনলোড
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        file_path = os.path.join(HOST_DIR, f"bot_{user_id}.py")
        log_path = os.path.join(HOST_DIR, f"log_{user_id}.txt")

        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        # আগের প্রসেস থাকলে টার্মিনেট
        if user_id in active_processes:
            try:
                active_processes[user_id].terminate()
            except Exception:
                pass

        # ব্যাকগ্রাউন্ড প্রসেস চালু করা
        try:
            log_file = open(log_path, "w")
            proc = subprocess.Popen(
                [sys.executable, file_path], 
                stdout=log_file, 
                stderr=log_file
            )
            active_processes[user_id] = proc
            
            time.sleep(3)
            
            # প্রসেস যদি বন্ধ হয়ে থাকে (error)
            if proc.poll() is not None:
                log_file.close()
                with open(log_path, "r") as f:
                    error_msg = f.read()
                
                err_snippet = error_msg[-800:] if error_msg else "Unknown Error (বট বন্ধ হয়ে গেছে)"
                
                bot.edit_message_text(
                    f"❌ **আপনার বটটি চালু হতে ব্যর্থ হয়েছে!**\n\n**এরর লগ (Error Log):**\n```text\n{err_snippet}\n```\n\n⚠️ কোডের ভুল বা মিসিং লাইব্রেরি ঠিক করে আবার আপলোড করুন।", 
                    message.chat.id, 
                    status_msg.message_id, 
                    parse_mode="Markdown"
                )
            else:
                log_file.close()
                bot.edit_message_text(
                    "🚀 **অভিনন্দন! আপনার পাইথন বটটি সফলভাবে ব্যাকগ্রাউন্ডে রান হয়েছে!**\n\nএখন আপনার বটের জায়গায় গিয়ে `/start` চেপে পরীক্ষা করুন।", 
                    message.chat.id, 
                    status_msg.message_id, 
                    parse_mode="Markdown"
                )

        except Exception as e:
            bot.edit_message_text(f"❌ সিস্টেম এরর: `{str(e)}`", message.chat.id, status_msg.message_id, parse_mode="Markdown")

        user_states[user_id] = None

# ================= রানার =================
if __name__ == "__main__":
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

import os
import sys
import time
import logging
import subprocess
import telebot
from telebot import types

# ================= সেটআপ =================
API_TOKEN = '8483362473:AAFqMixrkiuGnwozELnBZyl9-neGmY6y4UI'       # @BotFather থেকে পাওয়া টোকেন দিন
ADMIN_ID = 8289191009                    # আপনার আইডি
FORCE_CHANNEL = "@yonnel"           # আপনার চ্যানেল ইউজারনেম
SUPPORT_USERNAME = "@sabbir2850"  # আপনার সাপোর্ট ইউজারনেম

bot = telebot.TeleBot(API_TOKEN)

# ================= ডাটাবেজ ও ফোল্ডার সেটআপ =================
users_db = {}
payment_numbers = {"bkash": "01700000000", "nagad": "01800000000"}
auto_payment_gateways = {"bkash_api": "DISABLED", "nagad_api": "DISABLED"}

# ব্যাকগ্রাউন্ডে চলতে থাকা ইউজারের প্রসেসগুলোর লিস্ট
active_processes = {}
user_states = {}

# ইউজারদের পাঠানো কোড সেভ করার ডিরেক্টরি
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

# ডায়নামিক ইনলাইন কিবোর্ড (এডমিন প্যানেল শুধু আপনার জন্য দেখা যাবে)
def get_inline_menu(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🛒 Buy Plan", callback_data="buy_plan")
    btn2 = types.InlineKeyboardButton("🚀 Host My Bot", callback_data="host_bot")
    btn3 = types.InlineKeyboardButton("💬 Support Chat", callback_data="support_chat")
    btn4 = types.InlineKeyboardButton("ℹ️ FAQ", callback_data="faq")
    
    markup.add(btn1, btn2)
    markup.add(btn3, btn4)
    
    # শুধুমাত্র আপনার আইডি (ADMIN_ID) হলে বাটন যোগ হবে
    if user_id == ADMIN_ID:
        btn_admin = types.InlineKeyboardButton("🔐 Admin Panel", callback_data="admin_panel")
        markup.add(btn_admin)
        
    return markup

# মেসেজ বক্সের নিচে স্থায়ী বাটন (Permanent Keyboard)
def get_persistent_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("🛒 Buy Plan")
    btn2 = types.KeyboardButton("🚀 Host My Bot")
    btn3 = types.KeyboardButton("💬 Support")
    btn4 = types.KeyboardButton("ℹ️ FAQ")
    markup.add(btn1, btn2, btn3, btn4)
    return markup

# ================= /start কমান্ড =================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    if user_id not in users_db:
        users_db[user_id] = {"approved": False, "plan": None}

    if not check_force_sub(user_id):
        markup = types.InlineKeyboardMarkup()
        btn_channel = types.InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{FORCE_CHANNEL.replace('@','')}")
        btn_joined = types.InlineKeyboardButton("✅ Joined", callback_data="check_join")
        markup.add(btn_channel)
        markup.add(btn_joined)
        bot.send_message(
            message.chat.id, 
            f"⚠️ **বটটি ব্যবহার করতে আমাদের চ্যানেলে জয়েন করুন!**\n\nচ্যানেল: {FORCE_CHANNEL}", 
            parse_mode="Markdown", 
            reply_markup=markup
        )
        return

    bot.send_message(
        message.chat.id, 
        "👋 **স্বাগতম আমাদের Bot Hosting Engine এ!**\nনিচের মেনু থেকে সেবা বেছে নিন:", 
        parse_mode="Markdown", 
        reply_markup=get_persistent_keyboard()
    )
    bot.send_message(
        message.chat.id, 
        "📌 **Quick Menu:**", 
        reply_markup=get_inline_menu(user_id)
    )

# ================= ইনলাইন কলব্যাক =================
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    user_id = call.from_user.id

    if call.data == "check_join":
        if check_force_sub(user_id):
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(call.message.chat.id, "✅ ধন্যবাদ! এখন সেবাগুলো ব্যবহার করতে পারবেন।", reply_markup=get_persistent_keyboard())
            bot.send_message(call.message.chat.id, "📌 **Quick Menu:**", reply_markup=get_inline_menu(user_id))
        else:
            bot.answer_callback_query(call.id, "❌ আপনি এখনো চ্যানেলে জয়েন করেননি!", show_alert=True)

    elif call.data == "home":
        bot.edit_message_text("👋 **স্বাগতম আমাদের Bot Hosting Engine এ!**", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=get_inline_menu(user_id))

    elif call.data == "buy_plan":
        show_buy_plan_menu(call.message.chat.id, call.message.message_id)

    elif call.data == "buy_standard":
        pay_numbers_txt = "\n".join([f"📱 **{k.upper()}:** `{v}`" for k, v in payment_numbers.items()])
        pay_msg = f"💳 **পেমেন্ট নির্দেশিকা:**\n\nনিচের নাম্বারে সেন্ড মানি করুন:\n{pay_numbers_txt}\n\nটাকা পাঠানোর পর আপনার **TrxID (ট্রানজেকশন আইডি)** লিখে পাঠান:"
        bot.edit_message_text(pay_msg, call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        user_states[user_id] = "waiting_for_trx"

    elif call.data == "host_bot":
        show_host_bot_prompt(call.message.chat.id, user_id, call.id)

    elif call.data == "support_chat":
        show_support_info(call.message.chat.id)

    elif call.data == "faq":
        show_faq_info(call.message.chat.id)

    elif call.data == "admin_panel":
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ আপনার এই প্যানেলে এক্সেস নেই!", show_alert=True)
            return
        show_admin_dashboard(call.message.chat.id)

    elif call.data == "admin_numbers":
        msg = "📱 **বর্তমান নাম্বারসমূহ:**\n\n"
        for k, v in payment_numbers.items():
            msg += f"• **{k.upper()}:** `{v}`\n"
        msg += "\nনতুন নাম্বার দিতে লিখুন: `method:number`\n(যেমন: `bkash:01711223344`):"
        bot.send_message(call.message.chat.id, msg, parse_mode="Markdown")
        user_states[user_id] = "waiting_for_add_number"

    elif call.data == "admin_auto_pay":
        bot.send_message(call.message.chat.id, "⚙️ Auto Payment API সেট করতে লিখুন:\n`gateway:api_key`\n(যেমন: `bkash_api:SECRET_KEY_123`)", parse_mode="Markdown")
        user_states[user_id] = "waiting_for_auto_api"

    elif call.data == "admin_add_u":
        bot.send_message(call.message.chat.id, "➕ এক্সেস দিতে ইউজারের **Telegram Numeric ID** লিখুন:")
        user_states[user_id] = "waiting_for_manual_user_add"

    elif call.data == "admin_rem_u":
        bot.send_message(call.message.chat.id, "➖ এক্সেস সরাতে ইউজারের **Telegram Numeric ID** লিখুন:")
        user_states[user_id] = "waiting_for_manual_user_rem"

    elif call.data.startswith("app_"):
        _, target_id, p_name = call.data.split("_")
        users_db[int(target_id)] = {"approved": True, "plan": p_name}
        try:
            bot.send_message(int(target_id), "🎉 **অভিনন্দন!** আপনার পেমেন্ট ভেরিফাই হয়েছে এবং হোস্টিং এক্সেস এক্টিভ করা হয়েছে। এখন 'Host My Bot' বাটনে ক্লিক করে ফাইল আপলোড করতে পারেন।")
        except Exception:
            pass
        bot.edit_message_text(call.message.text + "\n\n✅ **APPROVED**", call.message.chat.id, call.message.message_id)

    elif call.data.startswith("rej_"):
        target_id = call.data.split("_")[1]
        try:
            bot.send_message(int(target_id), "❌ **পেমেন্ট তথ্য ভুল থাকায় বাতিল করা হয়েছে!**")
        except Exception:
            pass
        bot.edit_message_text(call.message.text + "\n\n❌ **REJECTED**", call.message.chat.id, call.message.message_id)

# ================= সাপোর্ট ফংশনসমূহ =================
def show_buy_plan_menu(chat_id, message_id=None):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Buy Standard Plan (100 BDT)", callback_data="buy_standard"))
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="home"))
    msg = "📜 **হোস্টিং প্ল্যান:**\n\n🔹 **Standard Host** - 100 BDT\n\nনিচে ক্লিক করে পেমেন্ট করুন:"
    if message_id:
        bot.edit_message_text(msg, chat_id, message_id, parse_mode="Markdown", reply_markup=markup)
    else:
        bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)

def show_host_bot_prompt(chat_id, user_id, callback_id=None):
    if not users_db.get(user_id, {}).get("approved", False):
        if callback_id:
            bot.answer_callback_query(callback_id, "❌ আপনার হোস্টিং এক্সেস নেই! আগে প্ল্যান কিনুন।", show_alert=True)
        else:
            bot.send_message(chat_id, "❌ আপনার হোস্টিং এক্সেস নেই! আগে প্ল্যান কিনুন।")
        return
    bot.send_message(chat_id, "📂 **আপনার পাইথন ফাইল (`.py`) টি আপলোড করুন:**\n\n*(ফাইলটি আপলোড করার পর সিস্টেম অটো চেক করবে কোড রান হচ্ছে কি না)*", parse_mode="Markdown")
    user_states[user_id] = "waiting_for_bot_file"

def show_support_info(chat_id):
    msg = f"💬 **সাপোর্ট সার্ভিস:**\n\nযেকোনো সমস্যায় আমাদের এডমিনের সাথে যোগাযোগ করুন:\n👤 Admin Username: {SUPPORT_USERNAME}\n\nঅথবা নিচে সরাসরি মেসেজ লিখুন (এডমিনকে ফরোয়ার্ড করা হবে):"
    bot.send_message(chat_id, msg, parse_mode="Markdown")
    user_states[chat_id] = "waiting_for_support"

def show_faq_info(chat_id):
    faq_text = (
        "ℹ️ **সাধারণ জিজ্ঞাসাসমূহ (FAQ):**\n\n"
        "❓ **১. কীভাবে বট হোস্ট করবেন?**\n"
        "👉 'Buy Plan' থেকে পেমেন্ট করুন। এপ্রুভ হলে 'Host My Bot' অপশনে গিয়ে `.py` ফাইল দিলে সরাসরি ব্যাকগ্রাউন্ডে রান শুরু হয়ে যাবে।\n\n"
        "❓ **২. বট কাজ না করলে কী করবেন?**\n"
        "👉 ফাইল পাঠানোর সাথে সাথেই আমাদের সিষ্টেম কোনো Error থাকলে আপনাকে সরাসরি এরর লগ পাঠিয়ে দেবে। সেই ভুল ঠিক করে আবার ফাইল দিন।\n\n"
        "❓ **৩. সাপোর্ট কোথায় পাবেন?**\n"
        "👉 '💬 Support' চেপে সরাসরি এডমিনের সাথে যোগাযোগ করতে পারবেন।"
    )
    bot.send_message(chat_id, faq_text, parse_mode="Markdown")

def show_admin_dashboard(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📱 Manage Numbers", callback_data="admin_numbers"),
        types.InlineKeyboardButton("⚙️ Setup Auto Payment API", callback_data="admin_auto_pay"),
        types.InlineKeyboardButton("➕ Add User Access", callback_data="admin_add_u"),
        types.InlineKeyboardButton("➖ Remove User Access", callback_data="admin_rem_u")
    )
    bot.send_message(chat_id, "🛠️ **Admin Dashboard Panel**", reply_markup=markup, parse_mode="Markdown")

# ================= ফাইল রিসিভ ও এরর চেকিং সহ ব্যাকগ্রাউন্ড রান =================
@bot.message_handler(content_types=['document'])
def handle_document(message):
    user_id = message.from_user.id
    state = user_states.get(user_id)

    if state == "waiting_for_bot_file":
        if not message.document.file_name.endswith('.py'):
            bot.reply_to(message, "❌ ভুল ফাইল! শুধুমাত্র পাইথন ফাইল (`.py`) আপলোড করুন।")
            return
        
        status_msg = bot.reply_to(message, "⏳ **আপনার ফাইল পরীক্ষা ও হোস্ট করা হচ্ছে...**", parse_mode="Markdown")

        # ১. ফাইল সেভ করা
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        file_path = os.path.join(HOST_DIR, f"bot_{user_id}.py")
        log_path = os.path.join(HOST_DIR, f"log_{user_id}.txt")

        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        # ২. আগের প্রসেস স্টপ করা
        if user_id in active_processes:
            try:
                active_processes[user_id].terminate()
            except Exception:
                pass

        # ৩. লগ ট্র্যাকিং সহ ব্যাকগ্রাউন্ডে প্রসেস রান করা
        try:
            log_file = open(log_path, "w")
            proc = subprocess.Popen(
                [sys.executable, file_path], 
                stdout=log_file, 
                stderr=log_file
            )
            active_processes[user_id] = proc
            
            # প্রসেসটি স্ট্যাবল কিনা চেক করার জন্য ৩ সেকেন্ড অপেক্ষা
            time.sleep(3)
            
            # প্রসেস যদি বন্ধ হয়ে গিয়ে থাকে (এরর এসেছে)
            if proc.poll() is not None:
                log_file.close()
                with open(log_path, "r") as f:
                    error_msg = f.read()
                
                err_snippet = error_msg[-800:] if error_msg else "Unknown Error (বট বন্ধ হয়ে গেছে)"
                
                bot.edit_message_text(
                    f"❌ **আপনার বটটি রান করতে ব্যর্থ হয়েছে!**\n\n**এরর লগ (Error Log):**\n```text\n{err_snippet}\n```\n\n⚠️ আপনার পাইথন কোডের ভুল অথবা মিসিং লাইব্রেরি ঠিক করে পুনরায় ফাইল আপলোড করুন।", 
                    message.chat.id, 
                    status_msg.message_id, 
                    parse_mode="Markdown"
                )
            else:
                log_file.close()
                bot.edit_message_text(
                    "🚀 **অভিনন্দন! আপনার পাইথন বটটি সফলভাবে ব্যাকগ্রাউন্ডে চালু হয়েছে!**\n\nএখন আপনার বটের ইউজারনেমে গিয়ে `/start` দিয়ে চেক করতে পারেন।", 
                    message.chat.id, 
                    status_msg.message_id, 
                    parse_mode="Markdown"
                )

        except Exception as e:
            bot.edit_message_text(f"❌ সিস্টেম এরর: `{str(e)}`", message.chat.id, status_msg.message_id, parse_mode="Markdown")

        user_states[user_id] = None

# ================= টেক্সট মেসেজ হ্যান্ডলার =================
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    text = message.text

    # স্থায়ী কিবোর্ড বাটন
    if text == "🛒 Buy Plan":
        show_buy_plan_menu(message.chat.id)
        return
    elif text == "🚀 Host My Bot":
        show_host_bot_prompt(message.chat.id, user_id)
        return
    elif text == "💬 Support":
        show_support_info(message.chat.id)
        return
    elif text == "ℹ️ FAQ":
        show_faq_info(message.chat.id)
        return

    state = user_states.get(user_id)

    if state == "waiting_for_trx":
        trx_id = text.strip()
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Approve", callback_data=f"app_{user_id}_Standard"),
            types.InlineKeyboardButton("❌ Reject", callback_data=f"rej_{user_id}")
        )
        bot.send_message(ADMIN_ID, f"📥 **নতুন পেমেন্ট রিকোয়েস্ট!**\n👤 User ID: `{user_id}`\n🧾 TrxID: `{trx_id}`", parse_mode="Markdown", reply_markup=markup)
        bot.reply_to(message, "✅ আপনার পেমেন্ট ট্রানজেকশন আইডি এডমিনের কাছে পাঠানো হয়েছে!")
        user_states[user_id] = None

    elif state == "waiting_for_support":
        bot.send_message(ADMIN_ID, f"📩 **Support Message:**\n{text}\n\nFrom User ID: `{user_id}`")
        bot.reply_to(message, "✅ বার্তাটি এডমিনের কাছে পাঠানো হয়েছে!")
        user_states[user_id] = None

    elif state == "waiting_for_add_number":
        try:
            method, num = text.strip().split(":")
            payment_numbers[method.lower()] = num
            bot.reply_to(message, f"✅ **{method.upper()}** নাম্বার সেট হয়েছে: `{num}`", parse_mode="Markdown")
        except Exception:
            bot.reply_to(message, "❌ ভুল ফরম্যাট! উদাহরণ: `bkash:01711223344`")
        user_states[user_id] = None

    elif state == "waiting_for_auto_api":
        try:
            gw, key = text.strip().split(":")
            auto_payment_gateways[gw.lower()] = key
            bot.reply_to(message, f"✅ **{gw.upper()}** API Key সেট হয়েছে!", parse_mode="Markdown")
        except Exception:
            bot.reply_to(message, "❌ ভুল ফরম্যাট! উদাহরণ: `bkash_api:SECRET_KEY`")
        user_states[user_id] = None

    elif state == "waiting_for_manual_user_add":
        try:
            target_id = int(text.strip())
            users_db[target_id] = {"approved": True, "plan": "Admin Granted"}
            bot.reply_to(message, f"✅ User ID `{target_id}` কে হোস্টিং এক্সেস দেওয়া হয়েছে!", parse_mode="Markdown")
        except Exception:
            bot.reply_to(message, "❌ সঠিক Numeric ID দিন!")
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
                bot.reply_to(message, f"✅ User ID `{target_id}` এর হোস্টিং এক্সেস বন্ধ করা হয়েছে এবং প্রসেস স্টপ করা হয়েছে!", parse_mode="Markdown")
            else:
                bot.reply_to(message, "❌ এই আইডি ডাটাবেজে পাওয়া যায়নি!")
        except Exception:
            bot.reply_to(message, "❌ সঠিক Numeric ID দিন!")
        user_states[user_id] = None

# ================= রানার =================
if __name__ == "__main__":
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

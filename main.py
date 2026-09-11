import os
import sys
import time
import subprocess
import telebot
from telebot import types
from datetime import datetime, timedelta

# ================= প্রাথমিক সেটআপ =================
API_TOKEN = '8483362473:AAFqMixrkiuGnwozELnBZyl9-neGmY6y4UI'  # @BotFather থেকে পাওয়া টোকেন দিন
OWNER_ID = 8289191009               # মূল ওনার এর আইডি

bot = telebot.TeleBot(API_TOKEN)

# ================= ডাইনামিক ডাটাবেজ (In-Memory Configuration) =================
# এগুলো সব এডমিন প্যানেল থেকে লাইভ পরিবর্তনযোগ্য
config_db = {
    "admins": [OWNER_ID],
    "owner_id": OWNER_ID,
    "force_channel": None,          # যেমন: "@yourchannel"
    "support_username": "Admin",    # যেমন: "YourTelegramUsername"
    "payment_numbers": {},          # {"bkash": "017...", "nagad": "018..."}
    "merchants": {}                 # {"rupantor": "API_KEY_HERE"}
}

# ইউজার ডাটাবেজ: {user_id: {"approved": True/False, "expire_at": datetime_obj, "plan": "Standard"}}
users_db = {}
active_processes = {}
user_states = {}

HOST_DIR = "./hosted_bots"
os.makedirs(HOST_DIR, exist_ok=True)

# ================= হেলপার ফাংশনসমূহ =================
def is_admin(user_id):
    return user_id in config_db["admins"] or user_id == config_db["owner_id"]

def check_force_sub(user_id):
    channel = config_db.get("force_channel")
    if not channel:
        return True
    try:
        member = bot.get_chat_member(channel, user_id)
        return member.status in ['creator', 'administrator', 'member']
    except Exception:
        return True

def is_user_active(user_id):
    u_data = users_db.get(user_id)
    if not u_data or not u_data.get("approved"):
        return False
    
    # মেয়াদ চেক
    expire_at = u_data.get("expire_at")
    if expire_at and datetime.now() > expire_at:
        # মেয়াদ শেষ! এক্সেস বন্ধ করা
        u_data["approved"] = False
        if user_id in active_processes:
            try:
                active_processes[user_id].terminate()
            except Exception:
                pass
        return False
    return True

def parse_time_duration(time_str):
    """ ১ মিনিট (1m), ২ ঘণ্টা (2h), ৩ দিন (3d) পার্স করার ফাংশন """
    try:
        unit = time_str[-1].lower()
        val = int(time_str[:-1])
        if unit == 'm':
            return timedelta(minutes=val)
        elif unit == 'h':
            return timedelta(hours=val)
        elif unit == 'd':
            return timedelta(days=val)
        else:
            return None
    except Exception:
        return None

# মেসেজ বক্সের নিচে স্থায়ী বাটন (Persistent Reply Keyboard)
def get_main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("🛒 Buy Plan")
    btn2 = types.KeyboardButton("🚀 Host My Bot")
    btn3 = types.KeyboardButton("💬 Support")
    btn4 = types.KeyboardButton("ℹ️ FAQ")
    btn5 = types.KeyboardButton("🔄 Bot Update")
    
    markup.add(btn1, btn2)
    markup.add(btn3, btn4)
    markup.add(btn5)
    
    # এডমিন হলে স্থায়ী বাটন যোগ হবে
    if is_admin(user_id):
        markup.add(types.KeyboardButton("🔐 Admin Panel"))
        
    return markup

# ================= /start কমান্ড =================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    if user_id not in users_db:
        users_db[user_id] = {"approved": False, "expire_at": None, "plan": None}

    # ফোর্স সাবস্ক্রিপশন চেক
    if not check_force_sub(user_id):
        channel = config_db["force_channel"]
        markup = types.InlineKeyboardMarkup()
        btn_channel = types.InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{channel.replace('@','')}")
        markup.add(btn_channel)
        bot.send_message(
            message.chat.id, 
            f"⚠️ **বটটি ব্যবহার করতে আমাদের চ্যানেলে জয়েন করুন!**\n\nচ্যানেল: {channel}", 
            parse_mode="Markdown", 
            reply_markup=markup
        )
        return

    bot.send_message(
        message.chat.id, 
        "👋 **স্বাগতম আমাদের Bot Hosting Engine এ!**\n\nনিচের মেনু থেকে আপনার সার্ভিস বেছে নিন:", 
        parse_mode="Markdown", 
        reply_markup=get_main_keyboard(user_id)
    )

# ================= টেক্সট ও স্থায়ী মেনু হ্যান্ডলিং =================
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    text = message.text

    # ১. Buy Plan
    if text == "🛒 Buy Plan":
        markup = types.InlineKeyboardMarkup(row_width=1)
        btn_manual = types.InlineKeyboardButton("📱 Manual Payment (Bkash/Nagad/Rocket)", callback_data="manual_pay")
        markup.add(btn_manual)
        
        # যদি অটো মার্চেন্ট গেটওয়ে সেট করা থাকে
        if config_db["merchants"]:
            btn_auto = types.InlineKeyboardButton("💳 Auto Payment Gateway", callback_data="auto_pay")
            markup.add(btn_auto)

        bot.send_message(
            message.chat.id, 
            "📜 **হোস্টিং প্ল্যান নির্বাচন করুন:**\n\n🔹 **Standard Host Plan**\n\nপেমেন্ট করতে নিচের বাটনে চাপুন:", 
            parse_mode="Markdown", 
            reply_markup=markup
        )
        return

    # ২. Host My Bot
    elif text == "🚀 Host My Bot":
        if not is_user_active(user_id):
            bot.send_message(message.chat.id, "❌ **আপনার হোস্টিং এক্সেস নেই অথবা মেয়াদ শেষ হয়ে গেছে!**\n\nপুনরায় এক্সেস নিতে '🛒 Buy Plan' এ যান।", parse_mode="Markdown")
            return
        
        expire_info = users_db[user_id]["expire_at"].strftime("%Y-%m-%d %H:%M:%S") if users_db[user_id].get("expire_at") else "Unlimited"
        bot.send_message(
            message.chat.id, 
            f"📂 **আপনার পাইথন ফাইল (`.py`) টি আপলোড করুন:**\n\n⏳ **আপনার প্যাকেজের মেয়াদ:** `{expire_info}`\n*(ফাইল আপলোড করলেই ব্যাকগ্রাউন্ডে রান হয়ে যাবে)*", 
            parse_mode="Markdown"
        )
        user_states[user_id] = "waiting_for_bot_file"
        return

    # ৩. Support (এডমিন প্যানেল থেকে সেট করা ইউজারনেমে ডাইরেক্ট মেসেজ লিঙ্ক)
    elif text == "💬 Support":
        supp_user = config_db.get("support_username", "Admin").replace("@", "")
        encoded_text = "Hello%20Admin,%20I%20need%20help%20regarding%20bot%20hosting."
        direct_inbox_url = f"https://t.me/{supp_user}?text={encoded_text}"
        
        markup = types.InlineKeyboardMarkup()
        btn_inbox = types.InlineKeyboardButton("📩 Direct Chat with Admin", url=direct_inbox_url)
        markup.add(btn_inbox)
        
        bot.send_message(
            message.chat.id, 
            f"💬 **সাপোর্ট সার্ভিস:**\n\nসহায়তার জন্য নিচের বাটনে ক্লিক করুন। সরাসরি এডমিন (`@{supp_user}`) ইনবক্সে ড্রাফট মেসেজসহ নিয়ে যাবে।", 
            parse_mode="Markdown", 
            reply_markup=markup
        )
        return

    # ৪. FAQ
    elif text == "ℹ️ FAQ":
        faq_text = (
            "ℹ️ **সাধারণ জিজ্ঞাসাসমূহ (FAQ):**\n\n"
            "❓ **১. কীভাবে বট হোস্ট করবেন?**\n"
            "👉 প্ল্যান কিনে এপ্রুভ হওয়ার পর '🚀 Host My Bot' চেপে পাইথন ফাইল পাঠালে সাথে সাথেই রানিং হয়ে যাবে।\n\n"
            "❓ **২. প্যাকেজের মেয়াদ শেষ হলে কী হবে?**\n"
            "👉 প্যাকেজের মেয়াদ শেষ হলে বট সার্ভিস স্বয়ংক্রিয়ভাবে বন্ধ হয়ে যাবে।"
        )
        bot.send_message(message.chat.id, faq_text, parse_mode="Markdown")
        return

    # ৫. Bot Update Button (ইউজারদের জন্য লোডিং অ্যানিমেশন)
    elif text == "🔄 Bot Update":
        status_msg = bot.send_message(message.chat.id, "🔄 **Checking Bot Engine Updates...**", parse_mode="Markdown")
        time.sleep(1.5)
        bot.edit_message_text("⚙️ **Syncing System Modules & Server Health...**", message.chat.id, status_msg.message_id, parse_mode="Markdown")
        time.sleep(1.5)
        bot.edit_message_text("✅ **Bot Engine Updated & Healthy!**\n\nসবকিছু সঠিকভাবে কাজ করছে।", message.chat.id, status_msg.message_id, parse_mode="Markdown")
        return

    # ৬. Admin Panel
    elif text == "🔐 Admin Panel":
        if not is_admin(user_id):
            bot.send_message(message.chat.id, "❌ আপনার এই প্যানেলে এক্সেস নেই!")
            return
        
        show_admin_main_dashboard(message.chat.id)
        return

    # ================= এডমিন ইনপুট হ্যান্ডলার (FSM State) =================
    state = user_states.get(user_id)

    if state == "waiting_for_trx":
        trx_id = text.strip()
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Approve With Validity", callback_data=f"appvalid_{user_id}"),
            types.InlineKeyboardButton("❌ Reject", callback_data=f"rej_{user_id}")
        )
        bot.send_message(config_db["owner_id"], f"📥 **নতুন ম্যানুয়াল পেমেন্ট রিকোয়েস্ট!**\n👤 User ID: `{user_id}`\n🧾 TrxID: `{trx_id}`", parse_mode="Markdown", reply_markup=markup)
        bot.reply_to(message, "✅ আপনার ট্রানজেকশন আইডি পাঠানো হয়েছে! এডমিন মেয়ادسহ এপ্রুভ করে দেবে।")
        user_states[user_id] = None

    elif state == "waiting_for_force_channel":
        ch = text.strip()
        if not ch.startswith("@"):
            ch = "@" + ch
        config_db["force_channel"] = ch
        bot.reply_to(message, f"✅ **Force Channel সেট করা হয়েছে:** `{ch}`", parse_mode="Markdown")
        user_states[user_id] = None

    elif state == "waiting_for_support_user":
        config_db["support_username"] = text.strip().replace("@", "")
        bot.reply_to(message, f"✅ **Support Username সেট হয়েছে:** `@{config_db['support_username']}`", parse_mode="Markdown")
        user_states[user_id] = None

    elif state == "waiting_for_add_num":
        try:
            method, num = text.strip().split(":")
            config_db["payment_numbers"][method.lower()] = num
            bot.reply_to(message, f"✅ **{method.upper()}** নাম্বার সেট করা হয়েছে: `{num}`", parse_mode="Markdown")
        except Exception:
            bot.reply_to(message, "❌ ভুল ফরম্যাট! সঠিক উদাহরণ: `bkash:01711223344`")
        user_states[user_id] = None

    elif state == "waiting_for_add_merchant":
        try:
            name, key = text.strip().split(":")
            config_db["merchants"][name.lower()] = key
            bot.reply_to(message, f"✅ **{name.upper()}** API Key সেট করা হয়েছে!", parse_mode="Markdown")
        except Exception:
            bot.reply_to(message, "❌ ভুল ফরম্যাট! সঠিক উদাহরণ: `rupantor:YOUR_API_KEY`")
        user_states[user_id] = None

    elif state == "waiting_for_grant_u_id":
        try:
            t_id = int(text.strip())
            user_states[user_id] = f"waiting_for_grant_u_time_{t_id}"
            bot.reply_to(message, f"⏱️ ইউজার `{t_id}` এর প্যাকেজের **মেয়াদ/সময়কাল** দিন:\n\nউদাহরণ:\n`30m` (30 মিনিট)\n`2h` (2 ঘণ্টা)\n`7d` (7 দিন)\n`30d` (30 দিন)", parse_mode="Markdown")
        except Exception:
            bot.reply_to(message, "❌ সঠিক Numeric User ID দিন!")

    elif state and state.startswith("waiting_for_grant_u_time_"):
        t_id = int(state.split("_")[-1])
        time_delta = parse_time_duration(text.strip())
        if time_delta:
            exp_time = datetime.now() + time_delta
            users_db[t_id] = {"approved": True, "expire_at": exp_time, "plan": "Manual Admin"}
            bot.reply_to(message, f"✅ User ID `{t_id}` কে হোস্টিং এক্সেস দেওয়া হয়েছে!\n⏳ **মেয়াদ শেষ:** `{exp_time.strftime('%Y-%m-%d %H:%M:%S')}`", parse_mode="Markdown")
            try:
                bot.send_message(t_id, f"🎉 **অভিনন্দন!** আপনাকে হোস্টিং এক্সেস দেওয়া হয়েছে।\n⏳ **মেয়াদ:** `{exp_time.strftime('%Y-%m-%d %H:%M:%S')}` পর্যন্ত।")
            except Exception:
                pass
            user_states[user_id] = None
        else:
            bot.reply_to(message, "❌ ভুল সময় ফরম্যাট! `30m`, `2h`, `7d` বা `30d` এভাবে দিন।")

    elif state and state.startswith("waiting_for_approve_validity_"):
        t_id = int(state.split("_")[-1])
        time_delta = parse_time_duration(text.strip())
        if time_delta:
            exp_time = datetime.now() + time_delta
            users_db[t_id] = {"approved": True, "expire_at": exp_time, "plan": "Standard"}
            bot.reply_to(message, f"✅ পেমেন্ট এপ্রুভ হয়েছে এবং ইউজার `{t_id}` এর মেয়াদ সেট করা হয়েছে!", parse_mode="Markdown")
            try:
                bot.send_message(t_id, f"🎉 **আপনার পেমেন্ট এপ্রুভ হয়েছে!**\n⏳ **প্যাকেজ মেয়াদ:** `{exp_time.strftime('%Y-%m-%d %H:%M:%S')}` পর্যন্ত।")
            except Exception:
                pass
            user_states[user_id] = None
        else:
            bot.reply_to(message, "❌ ভুল সময় ফরম্যাট! `1h`, `7d`, `30d` এভাবে দিন।")

    elif state == "waiting_for_rem_u":
        try:
            t_id = int(text.strip())
            if t_id in users_db:
                users_db[t_id]["approved"] = False
                if t_id in active_processes:
                    try:
                        active_processes[t_id].terminate()
                    except Exception:
                        pass
                bot.reply_to(message, f"✅ User ID `{t_id}` এর প্যাকেজ ও হোস্টিং বন্ধ করা হয়েছে!", parse_mode="Markdown")
            else:
                bot.reply_to(message, "❌ এই আইডি ডাটাবেজে নেই!")
        except Exception:
            bot.reply_to(message, "❌ সঠিক Numeric User ID দিন!")
        user_states[user_id] = None

    elif state == "waiting_for_add_admin":
        try:
            a_id = int(text.strip())
            if a_id not in config_db["admins"]:
                config_db["admins"].append(a_id)
            bot.reply_to(message, f"✅ User ID `{a_id}` কে নতুন **Admin** হিসেবে যুক্ত করা হয়েছে!", parse_mode="Markdown")
        except Exception:
            bot.reply_to(message, "❌ সঠিক Numeric User ID দিন!")
        user_states[user_id] = None

    elif state == "waiting_for_rem_admin":
        try:
            a_id = int(text.strip())
            if a_id in config_db["admins"] and a_id != config_db["owner_id"]:
                config_db["admins"].remove(a_id)
                bot.reply_to(message, f"✅ Admin ID `{a_id}` কে অ্যাডমিন তালিকা থেকে সরানো হয়েছে!", parse_mode="Markdown")
            else:
                bot.reply_to(message, "❌ এই আইডিটি সরান সম্ভব নয় (হয়তো ওনার আইডি বা তালিকায় নেই)!")
        except Exception:
            bot.reply_to(message, "❌ সঠিক Numeric User ID দিন!")
        user_states[user_id] = None

    elif state == "waiting_for_transfer_owner":
        try:
            new_o_id = int(text.strip())
            config_db["owner_id"] = new_o_id
            if new_o_id not in config_db["admins"]:
                config_db["admins"].append(new_o_id)
            bot.reply_to(message, f"👑 **বটের মূল ওনারশিপ সফলভাবে ট্রান্সফার করা হয়েছে User ID:** `{new_o_id}` এ!", parse_mode="Markdown")
        except Exception:
            bot.reply_to(message, "❌ সঠিক Numeric User ID দিন!")
        user_states[user_id] = None

# ================= এডমিন মেইন ড্যাশবোর্ড =================
def show_admin_main_dashboard(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📢 Force Channel", callback_data="adm_channel"),
        types.InlineKeyboardButton("💬 Support Username", callback_data="adm_support"),
        types.InlineKeyboardButton("📱 Payment Numbers", callback_data="adm_numbers"),
        types.InlineKeyboardButton("💳 Merchant API", callback_data="adm_merchants"),
        types.InlineKeyboardButton("➕ Grant Package", callback_data="adm_grant_u"),
        types.InlineKeyboardButton("➖ Remove Package", callback_data="adm_rem_u"),
        types.InlineKeyboardButton("👮 Add Admin", callback_data="adm_add_admin"),
        types.InlineKeyboardButton("❌ Remove Admin", callback_data="adm_rem_admin"),
        types.InlineKeyboardButton("👑 Transfer Ownership", callback_data="adm_transfer_owner")
    )
    bot.send_message(chat_id, "🛠️ **এডমিন অল-ইন-ওয়ান কন্ট্রোল প্যানেল**", parse_mode="Markdown", reply_markup=markup)

# ================= ইনলাইন কলব্যাক হ্যান্ডলার =================
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    user_id = call.from_user.id

    if call.data == "manual_pay":
        nums = config_db["payment_numbers"]
        if not nums:
            bot.send_message(call.message.chat.id, "❌ বর্তমানে কোনো ম্যানুয়াল পেমেন্ট নাম্বার সেট করা নেই। এডমিনের সাথে যোগাযোগ করুন।")
            return
        pay_numbers_txt = "\n".join([f"📱 **{k.upper()}:** `{v}`" for k, v in nums.items()])
        pay_msg = f"💳 **ম্যানুয়াল পেমেন্ট পদ্ধতি:**\n\nনিচের নাম্বারে টাকা পাঠান:\n{pay_numbers_txt}\n\nটাকা পাঠানোর পর আপনার **TrxID (ট্রানজেকশন আইডি)** লিখে মেসেজ দিন:"
        bot.send_message(call.message.chat.id, pay_msg, parse_mode="Markdown")
        user_states[user_id] = "waiting_for_trx"

    elif call.data == "adm_channel":
        markup = types.InlineKeyboardMarkup()
        if config_db["force_channel"]:
            markup.add(types.InlineKeyboardButton("❌ Delete Force Channel", callback_data="del_channel"))
        bot.send_message(call.message.chat.id, f"📢 **বর্তমান চ্যানেল:** `{config_db['force_channel']}`\n\nনতুন চ্যানেল সেট করতে Channel Username লিখুন (যেমন: `@mychannel`):", parse_mode="Markdown", reply_markup=markup)
        user_states[user_id] = "waiting_for_force_channel"

    elif call.data == "del_channel":
        config_db["force_channel"] = None
        bot.send_message(call.message.chat.id, "✅ Force Channel ডিলিট করা হয়েছে!")

    elif call.data == "adm_support":
        bot.send_message(call.message.chat.id, f"💬 **বর্তমান সাপোর্ট ইউজারনেম:** `@{config_db['support_username']}`\n\nনতুন Telegram Username দিন (@ ছাড়া):", parse_mode="Markdown")
        user_states[user_id] = "waiting_for_support_user"

    elif call.data == "adm_numbers":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("➕ Add/Update Number", callback_data="add_num"))
        if config_db["payment_numbers"]:
            markup.add(types.InlineKeyboardButton("🗑️ Clear All Numbers", callback_data="del_nums"))
        
        nums_txt = "\n".join([f"• **{k.upper()}:** `{v}`" for k, v in config_db["payment_numbers"].items()]) if config_db["payment_numbers"] else "নেই"
        bot.send_message(call.message.chat.id, f"📱 **পেমেন্ট নাম্বারসমূহ:**\n\n{nums_txt}", parse_mode="Markdown", reply_markup=markup)

    elif call.data == "add_num":
        bot.send_message(call.message.chat.id, "লিখুন: `method:number`\n(যেমন: `bkash:01700000000` বা `nagad:01800000000`):", parse_mode="Markdown")
        user_states[user_id] = "waiting_for_add_num"

    elif call.data == "del_nums":
        config_db["payment_numbers"] = {}
        bot.send_message(call.message.chat.id, "✅ সব পেমেন্ট নাম্বার রিমুভ করা হয়েছে!")

    elif call.data == "adm_merchants":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("➕ Set Merchant API Key", callback_data="add_merchant"))
        if config_db["merchants"]:
            markup.add(types.InlineKeyboardButton("🗑️ Clear Merchant API", callback_data="del_merchants"))
        bot.send_message(call.message.chat.id, f"💳 **মার্চেন্ট এপিআই:**\n`{config_db['merchants']}`", parse_mode="Markdown", reply_markup=markup)

    elif call.data == "add_merchant":
        bot.send_message(call.message.chat.id, "লিখুন: `gateway_name:api_key`\n(যেমন: `rupantor:SECRET_KEY_123`):", parse_mode="Markdown")
        user_states[user_id] = "waiting_for_add_merchant"

    elif call.data == "del_merchants":
        config_db["merchants"] = {}
        bot.send_message(call.message.chat.id, "✅ সব মার্চেন্ট API ডিলিট করা হয়েছে!")

    elif call.data == "adm_grant_u":
        bot.send_message(call.message.chat.id, "➕ প্যাকেজ দিতে ইউজারের **Telegram Numeric ID** লিখুন:")
        user_states[user_id] = "waiting_for_grant_u_id"

    elif call.data == "adm_rem_u":
        bot.send_message(call.message.chat.id, "➖ প্যাকেজ বাতিল করতে ইউজারের **Telegram Numeric ID** লিখুন:")
        user_states[user_id] = "waiting_for_rem_u"

    elif call.data == "adm_add_admin":
        bot.send_message(call.message.chat.id, "👮 নতুন এডমিন যোগ করতে ইউজারের **Telegram Numeric ID** লিখুন:")
        user_states[user_id] = "waiting_for_add_admin"

    elif call.data == "adm_rem_admin":
        bot.send_message(call.message.chat.id, "❌ এডমিন সরাতে ইউজারের **Telegram Numeric ID** লিখুন:")
        user_states[user_id] = "waiting_for_rem_admin"

    elif call.data == "adm_transfer_owner":
        if user_id != config_db["owner_id"]:
            bot.answer_callback_query(call.id, "❌ শুধুমাত্র মূল ওনার ওনারশিপ ট্রান্সফার করতে পারবেন!", show_alert=True)
            return
        bot.send_message(call.message.chat.id, "👑 **বটের মূল ওনারশিপ ট্রান্সফার করতে নতুন ওনারের Telegram Numeric ID দিন:**")
        user_states[user_id] = "waiting_for_transfer_owner"

    elif call.data.startswith("appvalid_"):
        target_u_id = int(call.data.split("_")[1])
        bot.send_message(call.message.chat.id, f"⏱️ ইউজার `{target_u_id}` এর পেমেন্টের জন্য **মেয়াদ/সময়কাল** লিখুন:\n\nউদাহরণ:\n`1h` (1 ঘণ্টা)\n`7d` (7 দিন)\n`30d` (30 দিন)", parse_mode="Markdown")
        user_states[user_id] = f"waiting_for_approve_validity_{target_u_id}"

    elif call.data.startswith("rej_"):
        target_u_id = call.data.split("_")[1]
        try:
            bot.send_message(int(target_u_id), "❌ **আপনার পেমেন্ট তথ্য ভুল থাকায় বাতিল করা হয়েছে!**")
        except Exception:
            pass
        bot.edit_message_text(call.message.text + "\n\n❌ **REJECTED**", call.message.chat.id, call.message.message_id)

# ================= ফাইল রিসিভ ও রান =================
@bot.message_handler(content_types=['document'])
def handle_document(message):
    user_id = message.from_user.id
    state = user_states.get(user_id)

    if state == "waiting_for_bot_file":
        if not message.document.file_name.endswith('.py'):
            bot.reply_to(message, "❌ ভুল ফাইল! শুধুমাত্র পাইথন ফাইল (`.py`) আপলোড করুন।")
            return
        
        status_msg = bot.reply_to(message, "⏳ **আপনার ফাইল সেভ ও রান করা হচ্ছে...**", parse_mode="Markdown")

        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        file_path = os.path.join(HOST_DIR, f"bot_{user_id}.py")
        log_path = os.path.join(HOST_DIR, f"log_{user_id}.txt")

        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        if user_id in active_processes:
            try:
                active_processes[user_id].terminate()
            except Exception:
                pass

        try:
            log_file = open(log_path, "w")
            proc = subprocess.Popen(
                [sys.executable, file_path], 
                stdout=log_file, 
                stderr=log_file
            )
            active_processes[user_id] = proc
            
            time.sleep(3)
            
            if proc.poll() is not None:
                log_file.close()
                with open(log_path, "r") as f:
                    error_msg = f.read()
                
                err_snippet = error_msg[-800:] if error_msg else "Unknown Error"
                bot.edit_message_text(
                    f"❌ **আপনার বটটি রান করতে ব্যর্থ হয়েছে!**\n\n**এরর লগ (Error Log):**\n```text\n{err_snippet}\n```\n\n⚠️ কোডের ভুল ঠিক করে পুনরায় আপলোড করুন।", 
                    message.chat.id, 
                    status_msg.message_id, 
                    parse_mode="Markdown"
                )
            else:
                log_file.close()
                bot.edit_message_text(
                    "🚀 **অভিনন্দন! আপনার পাইথন বটটি সফলভাবে ব্যাকগ্রাউন্ডে চালু হয়েছে!**\n\nএখন আপনার বটের ইউজারনেমে গিয়ে `/start` চেপে পরীক্ষা করুন।", 
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

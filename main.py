import os
import sys
import logging
import subprocess
import telebot
from telebot import types

# ================= সেটআপ =================
API_TOKEN = '8483362473:AAFqMixrkiuGnwozELnBZyl9-neGmY6y4UI'  # এখানে আপনার টোকেন বসান
ADMIN_ID = 8289191009               # আপনার অ্যাডমিন আইডি
FORCE_CHANNEL = "@yourchannel"      # আপনার চ্যানেলের ইউজারনেম (@ সহ)

bot = telebot.TeleBot(API_TOKEN)

# ================= ডাটাবেজ =================
users_db = {}
payment_numbers = {"bkash": "01700000000", "nagad": "01800000000"}
auto_payment_gateways = {"bkash_api": "DISABLED", "nagad_api": "DISABLED"}
active_processes = {}
user_states = {}

HOST_DIR = "./hosted_bots"
os.makedirs(HOST_DIR, exist_ok=True)

# ================= হেলপার =================
def check_force_sub(user_id):
    if not FORCE_CHANNEL or FORCE_CHANNEL == "@yourchannel":
        return True
    try:
        member = bot.get_chat_member(FORCE_CHANNEL, user_id)
        return member.status in ['creator', 'administrator', 'member']
    except Exception:
        return True

def main_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🛒 Buy Plan", callback_data="buy_plan")
    btn2 = types.InlineKeyboardButton("🚀 Host My Bot", callback_data="host_bot")
    btn3 = types.InlineKeyboardButton("💬 Support Chat", callback_data="support_chat")
    btn4 = types.InlineKeyboardButton("🔐 Admin Panel", callback_data="admin_panel")
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

    bot.send_message(message.chat.id, "👋 **স্বাগতম আমাদের Bot Hosting Engine এ!**\nনিচের মেনু থেকে সেবা বেছে নিন:", parse_mode="Markdown", reply_markup=main_keyboard())

# ================= কলব্যাক হ্যান্ডলার =================
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    user_id = call.from_user.id

    if call.data == "check_join":
        if check_force_sub(user_id):
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(call.message.chat.id, "✅ ধন্যবাদ! এখন সেবাগুলো ব্যবহার করতে পারবেন।", reply_markup=main_keyboard())
        else:
            bot.answer_callback_query(call.id, "❌ আপনি এখনো চ্যানেলে জয়েন করেননি!", show_alert=True)

    elif call.data == "home":
        bot.edit_message_text("👋 **স্বাগতম আমাদের Bot Hosting Engine এ!**", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=main_keyboard())

    elif call.data == "buy_plan":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Buy Standard Plan (100 BDT)", callback_data="buy_standard"))
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="home"))
        bot.edit_message_text("📜 **হোস্টিং প্ল্যান:**\n\n🔹 **Standard Host** - 100 BDT\n\nনিচে ক্লিক করে পেমেন্ট করুন:", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif call.data == "buy_standard":
        pay_numbers_txt = "\n".join([f"📱 **{k.upper()}:** `{v}`" for k, v in payment_numbers.items()])
        pay_msg = f"💳 **পেমেন্ট নির্দেশিকা:**\n\nনিচের নাম্বারে সেন্ড মানি করুন:\n{pay_numbers_txt}\n\nটাকা পাঠানোর পর আপনার **TrxID (ট্রানজেকশন আইডি)** লিখে পাঠান:"
        bot.edit_message_text(pay_msg, call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        user_states[user_id] = "waiting_for_trx"

    elif call.data == "host_bot":
        if not users_db.get(user_id, {}).get("approved", False):
            bot.answer_callback_query(call.id, "❌ আপনার হোস্টিং এক্সেস নেই! আগে প্ল্যান কিনুন।", show_alert=True)
            return
        bot.send_message(call.message.chat.id, "📂 **আপনার পাইথন ফাইল (`.py`) টি আপলোড করুন:**")
        user_states[user_id] = "waiting_for_bot_file"

    elif call.data == "support_chat":
        bot.send_message(call.message.chat.id, "💬 এডমিনের কাছে পাঠাতে চাওয়া বার্তাটি লিখুন:")
        user_states[user_id] = "waiting_for_support"

    elif call.data == "admin_panel":
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ আপনি এই প্যানেলের এডমিন নন!", show_alert=True)
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
            bot.send_message(int(target_id), "🎉 **অভিনন্দন!** আপনার পেমেন্ট ভেরিফাই হয়েছে এবং প্ল্যান একটিভ করা হয়েছে।")
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

# ================= ড্যাশবোর্ড =================
def show_admin_dashboard(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📱 Manage Numbers", callback_data="admin_numbers"),
        types.InlineKeyboardButton("⚙️ Setup Auto Payment API", callback_data="admin_auto_pay"),
        types.InlineKeyboardButton("➕ Add User Access", callback_data="admin_add_u"),
        types.InlineKeyboardButton("➖ Remove User Access", callback_data="admin_rem_u")
    )
    bot.send_message(chat_id, "🛠️ **Admin Dashboard Panel**", reply_markup=markup, parse_mode="Markdown")

# ================= ফাইল ও মেসেজ হ্যান্ডলার =================
@bot.message_handler(content_types=['document'])
def handle_document(message):
    user_id = message.from_user.id
    state = user_states.get(user_id)

    if state == "waiting_for_bot_file":
        if not message.document.file_name.endswith('.py'):
            bot.reply_to(message, "❌ ভুল ফাইল! শুধুমাত্র `.py` ফাইল পাঠাবেন।")
            return
        
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        file_path = os.path.join(HOST_DIR, f"bot_{user_id}.py")
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        if user_id in active_processes:
            try:
                active_processes[user_id].terminate()
            except Exception:
                pass

        proc = subprocess.Popen([sys.executable, file_path])
        active_processes[user_id] = proc
        bot.reply_to(message, "🚀 **আপনার ফাইলটি সার্ভারে সঠিকভাবে রান করা হয়েছে!**", parse_mode="Markdown")
        user_states[user_id] = None

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    state = user_states.get(user_id)

    if state == "waiting_for_trx":
        trx_id = message.text.strip()
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Approve", callback_data=f"app_{user_id}_Standard"),
            types.InlineKeyboardButton("❌ Reject", callback_data=f"rej_{user_id}")
        )
        bot.send_message(ADMIN_ID, f"📥 **নতুন পেমেন্ট রিকোয়েস্ট!**\n👤 User ID: `{user_id}`\n🧾 TrxID: `{trx_id}`", parse_mode="Markdown", reply_markup=markup)
        bot.reply_to(message, "✅ আপনার পেমেন্ট ইনফরমেশন এডমিনকে পাঠানো হয়েছে!")
        user_states[user_id] = None

    elif state == "waiting_for_support":
        bot.send_message(ADMIN_ID, f"📩 **Support Message:**\n{message.text}\n\nFrom User ID: `{user_id}`")
        bot.reply_to(message, "✅ বার্তাটি এডমিনের কাছে পাঠানো হয়েছে!")
        user_states[user_id] = None

    elif state == "waiting_for_add_number":
        try:
            method, num = message.text.strip().split(":")
            payment_numbers[method.lower()] = num
            bot.reply_to(message, f"✅ **{method.upper()}** নাম্বার সেট হয়েছে: `{num}`", parse_mode="Markdown")
        except Exception:
            bot.reply_to(message, "❌ ভুল ফরম্যাট! উদাহরণ: `bkash:01711223344`")
        user_states[user_id] = None

    elif state == "waiting_for_auto_api":
        try:
            gw, key = message.text.strip().split(":")
            auto_payment_gateways[gw.lower()] = key
            bot.reply_to(message, f"✅ **{gw.upper()}** API Key সেট হয়েছে!", parse_mode="Markdown")
        except Exception:
            bot.reply_to(message, "❌ ভুল ফরম্যাট! উদাহরণ: `bkash_api:SECRET_KEY`")
        user_states[user_id] = None

    elif state == "waiting_for_manual_user_add":
        try:
            target_id = int(message.text.strip())
            users_db[target_id] = {"approved": True, "plan": "Admin Granted"}
            bot.reply_to(message, f"✅ User ID `{target_id}` কে হোস্টিং এক্সেস দেওয়া হয়েছে!", parse_mode="Markdown")
        except Exception:
            bot.reply_to(message, "❌ সঠিক Numeric ID দিন!")
        user_states[user_id] = None

    elif state == "waiting_for_manual_user_rem":
        try:
            target_id = int(message.text.strip())
            if target_id in users_db:
                users_db[target_id]["approved"] = False
                if target_id in active_processes:
                    try:
                        active_processes[target_id].terminate()
                    except Exception:
                        pass
                bot.reply_to(message, f"✅ User ID `{target_id}` এর এক্সেস বন্ধ করা হয়েছে!", parse_mode="Markdown")
            else:
                bot.reply_to(message, "❌ এই আইডি ডাটাবেজে পাওয়া যায়নি!")
        except Exception:
            bot.reply_to(message, "❌ সঠিক Numeric ID দিন!")
        user_states[user_id] = None

# ================= রানার =================
if __name__ == "__main__":
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

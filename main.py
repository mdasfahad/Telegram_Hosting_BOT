import os
import logging
import asyncio
import subprocess
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery

# ================= সেটআপ (এখানে তথ্য দিন) =================
API_TOKEN = '8588997586:AAHEzsrXrzbeNZ9FzE3FV5G6XlGAU9UvvTA'   # @BotFather থেকে নেওয়া টোকেন
ADMIN_ID = 8289191009                 # আপনার টেলিগ্রাম নিউমেরিক আইডি
FORCE_CHANNEL = "@yourchannel"       # আপনার টেলিগ্রাম চ্যানেল ইউজারনেম

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ================= ডাটাবেজ ও ডিরেক্টরি =================
users_db = {}
payment_numbers = {"bkash": "01700000000", "nagad": "01800000000"}
auto_payment_gateways = {"bkash_api": "DISABLED", "nagad_api": "DISABLED"}
active_processes = {}

HOST_DIR = "./hosted_bots"
os.makedirs(HOST_DIR, exist_ok=True)

# ================= FSM স্টেটস =================
class Form(StatesGroup):
    waiting_for_trx = State()
    waiting_for_support = State()
    waiting_for_add_number = State()
    waiting_for_auto_api = State()
    waiting_for_manual_user_add = State()
    waiting_for_manual_user_rem = State()
    waiting_for_bot_file = State()

# ================= হেলপারস =================
async def check_force_sub(user_id: int) -> bool:
    if not FORCE_CHANNEL or FORCE_CHANNEL == "@yourchannel":
        return True
    try:
        member = await bot.get_chat_member(chat_id=FORCE_CHANNEL, user_id=user_id)
        return member.status in ['creator', 'administrator', 'member']
    except Exception:
        return True

def main_keyboard():
    kb = [
        [InlineKeyboardButton(text="🛒 Buy Plan", callback_data="buy_plan"), InlineKeyboardButton(text="🚀 Host My Bot", callback_data="host_bot")],
        [InlineKeyboardButton(text="💬 Support Chat", callback_data="support_chat"), InlineKeyboardButton(text="🔐 Admin Panel", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ================= স্টার্ট হ্যান্ডলার =================
@dp.message(Command("start"))
async def start_cmd(message: Message):
    user_id = message.from_user.id
    if user_id not in users_db:
        users_db[user_id] = {"approved": False, "plan": None}

    if not await check_force_sub(user_id):
        kb = [
            [InlineKeyboardButton(text="📢 Join Channel", url=f"https://t.me/{FORCE_CHANNEL.replace('@','')}")],
            [InlineKeyboardButton(text="✅ Joined", callback_data="check_join")]
        ]
        await message.answer(
            f"⚠️ **বটটি ব্যবহার করতে আমাদের চ্যানেলে জয়েন করুন!**\n\nচ্যানেল: {FORCE_CHANNEL}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
            parse_mode="Markdown"
        )
        return

    await message.answer("👋 **স্বাগতম আমাদের Bot Hosting Engine এ!**\nনিচের মেনু থেকে অপশন নির্বাচন করুন:", reply_markup=main_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data == "check_join")
async def check_join_callback(callback: CallbackQuery):
    if await check_force_sub(callback.from_user.id):
        await callback.message.delete()
        await callback.message.answer("✅ ধন্যবাদ! এখন আপনি পরিষেবা ব্যবহার করতে পারবেন।", reply_markup=main_keyboard())
    else:
        await callback.answer("❌ আপনি এখনো চ্যানেলে জয়েন করেননি!", show_alert=True)

# ================= প্ল্যান ও পেমেন্ট =================
@dp.callback_query(F.data == "buy_plan")
async def show_plans(callback: CallbackQuery):
    msg = "📜 **হোস্টিং প্ল্যান:**\n\n🔹 **Standard Host** - 100 BDT\n\nনিচে ক্লিক করে পেমেন্ট করুন:"
    kb = [
        [InlineKeyboardButton(text="Buy Standard Plan", callback_data="buy_standard")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="home")]
    ]
    await callback.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")

@dp.callback_query(F.data == "home")
async def go_home(callback: CallbackQuery):
    await callback.message.edit_text("👋 **স্বাগতম আমাদের Bot Hosting Engine এ!**", reply_markup=main_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data == "buy_standard")
async def process_buy(callback: CallbackQuery, state: FSMContext):
    await state.update_data(selected_plan="Standard Host")
    pay_numbers_txt = "\n".join([f"📱 **{k.upper()}:** `{v}`" for k, v in payment_numbers.items()])
    pay_msg = f"💳 **পেমেন্ট নির্দেশিকা:**\n\nনিচের নাম্বারে সেন্ড মানি করুন:\n{pay_numbers_txt}\n\nটাকা পাঠানোর পর **TrxID (ট্রানজেকশন আইডি)** লিখে পাঠান:"
    await callback.message.edit_text(pay_msg, parse_mode="Markdown")
    await state.set_state(Form.waiting_for_trx)

@dp.message(Form.waiting_for_trx)
async def receive_trx(message: Message, state: FSMContext):
    trx_id = message.text.strip()
    kb = [[InlineKeyboardButton(text="✅ Approve", callback_data=f"app_{message.from_user.id}_Standard"), InlineKeyboardButton(text="❌ Reject", callback_data=f"rej_{message.from_user.id}")]]
    await bot.send_message(ADMIN_ID, f"📥 **নতুন পেমেন্ট রিকোয়েস্ট!**\n👤 User ID: `{message.from_user.id}`\n🧾 TrxID: `{trx_id}`", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")
    await message.answer("✅ আপনার পেমেন্ট ইনফরমেশন পাঠানো হয়েছে! ভেরিফাই হলে প্ল্যান চালু হবে।")
    await state.clear()

# ================= বট হোস্টিং (ফাইল রান) =================
@dp.callback_query(F.data == "host_bot")
async def start_hosting(callback: CallbackQuery, state: FSMContext):
    u_id = callback.from_user.id
    if not users_db.get(u_id, {}).get("approved", False):
        await callback.answer("❌ আপনার হোস্টিং এক্সেস নেই! আগে প্ল্যান কিনুন।", show_alert=True)
        return
    await callback.message.answer("📂 **আপনার পাইথন ফাইল (`.py`) টি আপলোড করুন:**")
    await state.set_state(Form.waiting_for_bot_file)

@dp.message(Form.waiting_for_bot_file)
async def process_bot_file(message: Message, state: FSMContext):
    if not message.document or not message.document.file_name.endswith(".py"):
        await message.answer("❌ ভুল ফাইল! শুধুমাত্র পাইথন `.py` ফাইল আপলোড করুন।")
        return
    
    u_id = message.from_user.id
    file_path = os.path.join(HOST_DIR, f"bot_{u_id}.py")
    
    file_info = await bot.get_file(message.document.file_id)
    await bot.download_file(file_info.file_path, file_path)

    if u_id in active_processes:
        try:
            active_processes[u_id].terminate()
        except Exception:
            pass

    proc = subprocess.Popen(["python", file_path])
    active_processes[u_id] = proc
    await message.answer("🚀 **আপনার ফাইল আপলোড করা হয়েছে এবং সার্ভারে রান করা হয়েছে!**")
    await state.clear()

# ================= সাপোর্ট চ্যাট =================
@dp.callback_query(F.data == "support_chat")
async def support_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("💬 এডমিনের কাছে পাঠাতে চাওয়া বার্তাটি লিখুন:")
    await state.set_state(Form.waiting_for_support)

@dp.message(Form.waiting_for_support)
async def send_support_msg(message: Message, state: FSMContext):
    await bot.send_message(ADMIN_ID, f"📩 **Support Message:** {message.text}\nFrom User ID: `{message.from_user.id}`")
    await message.answer("✅ বার্তাটি এডমিনের কাছে সফলভাবে পাঠানো হয়েছে!")
    await state.clear()

# ================= এডমিন প্যানেল (2FA ছাড়া সরাসরি এক্সেস) =================
@dp.callback_query(F.data == "admin_panel")
async def admin_entry(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ আপনি এই প্যানেলের এডমিন নন!", show_alert=True)
        return
    await show_admin_dashboard(callback.message)

async def show_admin_dashboard(message: Message):
    kb = [
        [InlineKeyboardButton(text="📱 Manage Numbers", callback_data="admin_numbers")],
        [InlineKeyboardButton(text="⚙️ Setup Auto Payment API", callback_data="admin_auto_pay")],
        [InlineKeyboardButton(text="➕ Add User Access", callback_data="admin_add_u"), InlineKeyboardButton(text="➖ Remove User Access", callback_data="admin_rem_u")]
    ]
    await message.answer("🛠️ **Admin Dashboard Panel**", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# ম্যানুয়াল পেমেন্ট নাম্বার পরিবর্তন
@dp.callback_query(F.data == "admin_numbers")
async def admin_numbers_menu(callback: CallbackQuery, state: FSMContext):
    msg = "📱 **বর্তমান নাম্বারসমূহ:**\n\n"
    for k, v in payment_numbers.items():
        msg += f"• **{k.upper()}:** `{v}`\n"
    msg += "\nনতুন নাম্বার যোগ/পরিবর্তন করতে লিখুন: `method:number`\n(যেমন: `bkash:01711223344`):"
    
    await callback.message.answer(msg, parse_mode="Markdown")
    await state.set_state(Form.waiting_for_add_number)

@dp.message(Form.waiting_for_add_number)
async def save_manual_number(message: Message, state: FSMContext):
    try:
        method, num = message.text.strip().split(":")
        payment_numbers[method.lower()] = num
        await message.answer(f"✅ **{method.upper()}** নাম্বার পরিবর্তন হয়ে `{num}` সেট হয়েছে!")
    except Exception:
        await message.answer("❌ ফরম্যাট ভুল! সঠিক নিয়ম: `bkash:01711223344`")
    await state.clear()

# অটো পেমেন্ট API কাস্টমাইজেশন
@dp.callback_query(F.data == "admin_auto_pay")
async def admin_auto_pay(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("⚙️ Auto Payment API কি (Key) পরিবর্তন করতে টাইপ করুন:\n`gateway:api_key`\n(যেমন: `bkash_api:SECRET_KEY_123`)", parse_mode="Markdown")
    await state.set_state(Form.waiting_for_auto_api)

@dp.message(Form.waiting_for_auto_api)
async def save_auto_api(message: Message, state: FSMContext):
    try:
        gw, key = message.text.strip().split(":")
        auto_payment_gateways[gw.lower()] = key
        await message.answer(f"✅ **{gw.upper()}** API Key সেটআপ সফল হয়েছে!")
    except Exception:
        await message.answer("❌ ফরম্যাট ভুল! সঠিক নিয়ম: `bkash_api:SECRET_KEY`")
    await state.clear()

# ম্যানুয়ালি ইউজার যুক্ত করা
@dp.callback_query(F.data == "admin_add_u")
async def admin_add_u_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("➕ এক্সেস দিতে ইউজারের **Telegram Numeric ID** লিখুন:")
    await state.set_state(Form.waiting_for_manual_user_add)

@dp.message(Form.waiting_for_manual_user_add)
async def save_add_user(message: Message, state: FSMContext):
    try:
        u_id = int(message.text.strip())
        users_db[u_id] = {"approved": True, "plan": "Admin Granted"}
        await message.answer(f"✅ User ID `{u_id}` কে হোস্টিং এক্সেস দেওয়া হয়েছে!")
    except Exception:
        await message.answer("❌ সঠিক Numeric User ID লিখুন!")
    await state.clear()

# ইউজার এক্সেস রিমুভ করা
@dp.callback_query(F.data == "admin_rem_u")
async def admin_rem_u_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("➖ এক্সেস সরাতে ইউজারের **Telegram Numeric ID** লিখুন:")
    await state.set_state(Form.waiting_for_manual_user_rem)

@dp.message(Form.waiting_for_manual_user_rem)
async def save_rem_user(message: Message, state: FSMContext):
    try:
        u_id = int(message.text.strip())
        if u_id in users_db:
            users_db[u_id]["approved"] = False
            if u_id in active_processes:
                try:
                    active_processes[u_id].terminate()
                except Exception:
                    pass
            await message.answer(f"✅ User ID `{u_id}` এর হোস্টিং এক্সেস বন্ধ করা হয়েছে!")
        else:
            await message.answer("❌ এই আইডি পাওয়া যায়নি!")
    except Exception:
        await message.answer("❌ সঠিক Numeric User ID লিখুন!")
    await state.clear()

# পেমেন্ট এপ্রুভ বা রিজেক্ট
@dp.callback_query(F.data.startswith("app_"))
async def approve_payment(callback: CallbackQuery):
    _, u_id, p_name = callback.data.split("_")
    users_db[int(u_id)] = {"approved": True, "plan": p_name}
    try:
        await bot.send_message(int(u_id), "🎉 **অভিনন্দন!** আপনার পেমেন্ট ভেরিফাই হয়েছে এবং প্ল্যান একটিভ করা হয়েছে।")
    except Exception:
        pass
    await callback.message.edit_text(callback.message.text + "\n\n✅ **APPROVED**")

@dp.callback_query(F.data.startswith("rej_"))
async def reject_payment(callback: CallbackQuery):
    u_id = callback.data.split("_")[1]
    try:
        await bot.send_message(int(u_id), "❌ **পেমেন্ট তথ্য ভুল থাকায় বাতিল করা হয়েছে!**")
    except Exception:
        pass
    await callback.message.edit_text(callback.message.text + "\n\n❌ **REJECTED**")

# ================= মেন রানার =================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

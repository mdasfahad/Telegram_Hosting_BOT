import os
import logging
import asyncio
import subprocess
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery, FSInputFile

# ================= CONFIGURATION =================
API_TOKEN = '8887776189:AAEDm4lDIiqkeLYSai3AqwwLhy-d94dAnnM'  # @BotFather থেকে নেওয়া টোকেন দিন
ADMIN_ID = 8289191009  # আপনার টেলিগ্রাম নিউমেরিক আইডি দিন
FORCE_CHANNEL = "@yourchannelusername"  # চ্যানেলের ইউজারনেম (@ সহ)
ADMIN_2FA_PIN = "1234"  # সিকিউরিটি পিন

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ================= DATABASE & STORAGE =================
users_db = {}  # {user_id: {"approved": False, "plan": None}}
plans_db = {
    "1": {"name": "Basic Host", "price": "100 BDT", "desc": "1 Bot | 512MB RAM"},
    "2": {"name": "Pro Host", "price": "250 BDT", "desc": "3 Bots | 2GB RAM"}
}
# Dynamic Admin Settings
payment_numbers = {"bkash": "01700000000", "nagad": "01800000000"}
auto_payment_gateways = {"bkash_api": "DISABLED", "nagad_api": "DISABLED"}
active_processes = {} # {user_id: process_instance}
admin_2fa_auth = set()

# Host Directory
HOST_DIR = "./hosted_bots"
os.makedirs(HOST_DIR, exist_ok=True)

# ================= FSM STATES =================
class Form(StatesGroup):
    waiting_for_trx = State()
    waiting_for_support = State()
    waiting_for_broadcast = State()
    waiting_for_2fa = State()
    waiting_for_add_number = State()
    waiting_for_auto_api = State()
    waiting_for_manual_user_add = State()
    waiting_for_manual_user_rem = State()
    waiting_for_bot_file = State()

# ================= HELPER FUNCTIONS =================
async def check_force_sub(user_id: int) -> bool:
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

# ================= START COMMAND & FORCE SUB =================
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

    await message.answer("👋 **স্বাগতম আমাদের Bot Hosting Engine এ!**\nনিচের অপশন থেকে সার্ভিস বেছে নিন:", reply_markup=main_keyboard(), parse_mode="Markdown")

@dp.callback_query(lambda c: c.data == "check_join")
async def check_join_callback(callback: CallbackQuery):
    if await check_force_sub(callback.from_user.id):
        await callback.message.delete()
        await callback.message.answer("✅ ধন্যবাদ! এখন আপনি বট ব্যবহার করতে পারবেন।", reply_markup=main_keyboard())
    else:
        await callback.answer("❌ আপনি এখনো চ্যানেলে জয়েন করেননি!", show_alert=True)

# ================= PLAN & PAYMENT SYSTEM =================
@dp.callback_query(lambda c: c.data == "buy_plan")
async def show_plans(callback: CallbackQuery):
    msg = "📜 **উপলব্ধ হোস্টিং প্ল্যানসমূহ:**\n\n"
    kb = []
    for p_id, p_info in plans_db.items():
        msg += f"🔹 **{p_info['name']}** - {p_info['price']}\n   _{p_info['desc']}_\n\n"
        kb.append([InlineKeyboardButton(text=f"Buy {p_info['name']}", callback_data=f"buy_{p_id}")])
    
    kb.append([InlineKeyboardButton(text="🔙 Back", callback_data="home")])
    await callback.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")

@dp.callback_query(lambda c: c.data.startswith("buy_"))
async def process_buy(callback: CallbackQuery, state: FSMContext):
    plan_id = callback.data.split("_")[1]
    plan = plans_db.get(plan_id)
    await state.update_data(selected_plan=plan['name'])

    pay_numbers_txt = "\n".join([f"📱 **{k.upper()}:** `{v}`" for k, v in payment_numbers.items()])
    pay_msg = (
        f"💳 **পেমেন্ট নির্দেশিকা ({plan['name']})**\n\n"
        f"💰 **মূল্য:** {plan['price']}\n\n"
        f"নিচের যেকোনো নাম্বারে টাকা সেন্ড মানি করুন:\n{pay_numbers_txt}\n\n"
        f"টাকা পাঠানোর পর নিচে আপনার **TrxID (ট্রানজেকশন আইডি)** লিখে পাঠান:"
    )
    await callback.message.edit_text(pay_msg, parse_mode="Markdown")
    await state.set_state(Form.waiting_for_trx)

@dp.message(Form.waiting_for_trx)
async def receive_trx(message: Message, state: FSMContext):
    user_data = await state.get_data()
    plan_name = user_data.get("selected_plan")
    trx_id = message.text.strip()

    kb = [
        [InlineKeyboardButton(text="✅ Approve", callback_data=f"app_{message.from_user.id}_{plan_name}"),
         InlineKeyboardButton(text="❌ Reject", callback_data=f"rej_{message.from_user.id}")]
    ]
    await bot.send_message(
        ADMIN_ID,
        f"📥 **নতুন পেমেন্ট রিকোয়েস্ট!**\n\n👤 **User:** {message.from_user.full_name} (`{message.from_user.id}`)\n📦 **Plan:** {plan_name}\n🧾 **TrxID:** `{trx_id}`",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="Markdown"
    )

    await message.answer("✅ আপনার পেমেন্ট ইনফরমেশন পাঠানো হয়েছে! এডমিন ভেরিফাই করলে প্ল্যান চালু হয়ে যাবে।")
    await state.clear()

# ================= BOT HOSTING ENGINE =================
@dp.callback_query(lambda c: c.data == "host_bot")
async def start_hosting(callback: CallbackQuery, state: FSMContext):
    u_id = callback.from_user.id
    if not users_db.get(u_id, {}).get("approved", False):
        await callback.answer("❌ আপনার কোনো একটিভ হোস্টিং প্ল্যান নেই! প্লিজ প্ল্যান কিনে নিন।", show_alert=True)
        return

    await callback.message.answer("📂 **আপনার পাইথন কোড ফাইল (`.py`) এখানে আপলোড করুন:**")
    await state.set_state(Form.waiting_for_bot_file)

@dp.message(Form.waiting_for_bot_file)
async def process_bot_file(message: Message, state: FSMContext):
    if not message.document or not message.document.file_name.endswith(".py"):
        await message.answer("❌ শুধুমাত্র পাইথন `.py` ফাইল আপলোড করুন!")
        return

    u_id = message.from_user.id
    file_path = os.path.join(HOST_DIR, f"bot_{u_id}.py")
    
    file_info = await bot.get_file(message.document.file_id)
    await bot.download_file(file_info.file_path, file_path)

    # Terminate existing bot if running
    if u_id in active_processes:
        active_processes[u_id].terminate()

    # Start new Python Process
    proc = subprocess.Popen(["python3", file_path])
    active_processes[u_id] = proc

    await message.answer("🚀 **আপনার বট সফলভাবে হোস্ট এবং রান করা হয়েছে!**")
    await state.clear()

# ================= LIVE SUPPORT =================
@dp.callback_query(lambda c: c.data == "support_chat")
async def support_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("💬 এডমিনকে পাঠাতে চাওয়া আপনার কাস্টম মেসেজটি লিখুন:")
    await state.set_state(Form.waiting_for_support)

@dp.message(Form.waiting_for_support)
async def send_support_msg(message: Message, state: FSMContext):
    await bot.send_message(
        ADMIN_ID,
        f"📩 **Support Msg from** {message.from_user.full_name} (`{message.from_user.id}`):\n\n{message.text}"
    )
    await message.answer("✅ আপনার মেসেজটি পাঠানো হয়েছে!")
    await state.clear()

# ================= ADMIN PANEL & DYNAMIC CONFIG =================
@dp.callback_query(lambda c: c.data == "admin_panel")
async def admin_entry(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ আপনার এক্সেস নেই!", show_alert=True)
        return

    if callback.from_user.id not in admin_2fa_auth:
        await callback.message.answer("🔐 **2FA Security Required:** সিকিউরিটি PIN দিন:")
        await state.set_state(Form.waiting_for_2fa)
        return

    await show_admin_dashboard(callback.message)

@dp.message(Form.waiting_for_2fa)
async def verify_2fa(message: Message, state: FSMContext):
    if message.text.strip() == ADMIN_2FA_PIN:
        admin_2fa_auth.add(message.from_user.id)
        await message.answer("🔓 **2FA Verified!**")
        await state.clear()
        await show_admin_dashboard(message)
    else:
        await message.answer("❌ ভুল PIN! আবার চেষ্টা করুন।")

async def show_admin_dashboard(message: Message):
    kb = [
        [InlineKeyboardButton(text="📱 Manage Manual Numbers", callback_data="admin_numbers")],
        [InlineKeyboardButton(text="⚙️ Setup Auto Payment API", callback_data="admin_auto_pay")],
        [InlineKeyboardButton(text="➕ Add User Access", callback_data="admin_add_u"), InlineKeyboardButton(text="➖ Remove User", callback_data="admin_rem_u")],
        [InlineKeyboardButton(text="📢 Broadcast Message", callback_data="admin_broadcast")]
    ]
    await message.answer("🛠️ **Admin Control Dashboard**", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# Manual Number Setup
@dp.callback_query(lambda c: c.data == "admin_numbers")
async def admin_numbers_menu(callback: CallbackQuery, state: FSMContext):
    msg = "📱 **বর্তমান পেমেন্ট নাম্বারসমূহ:**\n\n"
    for k, v in payment_numbers.items():
        msg += f"• **{k.upper()}:** `{v}`\n"
    msg += "\nনতুন নাম্বার এড করতে লিখন: `method name:number` (যেমন: `bkash:01711223344`):"
    
    await callback.message.answer(msg, parse_mode="Markdown")
    await state.set_state(Form.waiting_for_add_number)

@dp.message(Form.waiting_for_add_number)
async def save_manual_number(message: Message, state: FSMContext):
    try:
        method, num = message.text.strip().split(":")
        payment_numbers[method.lower()] = num
        await message.answer(f"✅ **{method.upper()}** নাম্বার পরিবর্তন করে `{num}` করা হয়েছে!")
    except Exception:
        await message.answer("❌ ফরম্যাট ভুল! সঠিক নিয়ম: `bkash:01711223344`")
    await state.clear()

# Auto Payment Setup
@dp.callback_query(lambda c: c.data == "admin_auto_pay")
async def admin_auto_pay(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("⚙️ Auto Payment API Credential সেটআপ করতে টাইপ করুন:\n`gateway_name:api_key` (যেমন: `bkash_api:SECRET_KEY_123`)")
    await state.set_state(Form.waiting_for_auto_api)

@dp.message(Form.waiting_for_auto_api)
async def save_auto_api(message: Message, state: FSMContext):
    try:
        gw, key = message.text.strip().split(":")
        auto_payment_gateways[gw.lower()] = key
        await message.answer(f"✅ **{gw.upper()}** অটো পেমেন্ট API সফলভাবে আপডেট করা হয়েছে!")
    except Exception:
        await message.answer("❌ ফরম্যাট ভুল! সঠিক নিয়ম: `bkash_api:SECRET_KEY`")
    await state.clear()

# Manual Add / Remove User
@dp.callback_query(lambda c: c.data == "admin_add_u")
async def admin_add_u_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("➕ এক্সেস দিতে ইউজারের **Telegram Numeric ID** লিখুন:")
    await state.set_state(Form.waiting_for_manual_user_add)

@dp.message(Form.waiting_for_manual_user_add)
async def save_add_user(message: Message, state: FSMContext):
    try:
        u_id = int(message.text.strip())
        users_db[u_id] = {"approved": True, "plan": "Admin Grant"}
        await message.answer(f"✅ User ID `{u_id}` কে সফলভাবে এক্সেস দেওয়া হয়েছে!")
        await bot.send_message(u_id, "🎉 এডমিন আপনাকে হোস্টিং ব্যবহারের এক্সেস প্রদান করেছে!")
    except Exception:
        await message.answer("❌ সঠিক Numeric User ID লিখুন!")
    await state.clear()

@dp.callback_query(lambda c: c.data == "admin_rem_u")
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
                active_processes[u_id].terminate()
            await message.answer(f"✅ User ID `{u_id}` এর এক্সেস বাতিল করা হয়েছে!")
            await bot.send_message(u_id, "⚠️ আপনার হোস্টিং এক্সেস রিমুভ করা হয়েছে।")
        else:
            await message.answer("❌ ইউজার ডাটাবেজে পাওয়া যায়নি!")
    except Exception:
        await message.answer("❌ সঠিক Numeric User ID লিখুন!")
    await state.clear()

# Payment Approvals
@dp.callback_query(lambda c: c.data.startswith("app_"))
async def approve_payment(callback: CallbackQuery):
    _, u_id, p_name = callback.data.split("_")
    users_db[int(u_id)] = {"approved": True, "plan": p_name}
    await bot.send_message(int(u_id), f"🎉 **অভিনন্দন!** আপনার **{p_name}** প্ল্যান চালু হয়েছে।")
    await callback.message.edit_text(callback.message.text + "\n\n✅ **APPROVED**")

@dp.callback_query(lambda c: c.data.startswith("rej_"))
async def reject_payment(callback: CallbackQuery):
    u_id = callback.data.split("_")[1]
    await bot.send_message(int(u_id), "❌ **দুঃখিত!** পেমেন্ট তথ্য ভুল থাকায় বাতিল করা হয়েছে।")
    await callback.message.edit_text(callback.message.text + "\n\n❌ **REJECTED**")

# ================= MAIN RUNNER =================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

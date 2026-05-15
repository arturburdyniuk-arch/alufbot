import asyncio
import logging
import os
import sqlite3

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    FSInputFile
)

# -------------------
# ENV
# -------------------

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not TOKEN:
    raise Exception("BOT_TOKEN missing")

logging.basicConfig(level=logging.INFO)

# -------------------
# BOT
# -------------------

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

# -------------------
# DB
# -------------------

conn = sqlite3.connect("crm.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS bikes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    price TEXT,
    description TEXT,
    photo TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bike TEXT,
    name TEXT,
    phone TEXT,
    user_id INTEGER,
    status TEXT DEFAULT 'new'
)
""")

conn.commit()


def seed():
    cur.execute("SELECT COUNT(*) FROM bikes")
    if cur.fetchone()[0] > 0:
        return

    bikes = [
        ("DUOTTS S26", "1760 Kč / week", "Мощный универсальный электровелосипед", "photos/bike1.jpg"),
        ("DUOTTS C29", "1440 Kč / week", "Комфортный велосипед для города", "photos/bike2.jpg"),
        ("DUOTTS C29K 2 Battery", "1490 Kč / week", "С двумя батареями", "photos/bike3.jpg"),
        ("Onesport OT08 Pro", "1600 Kč / week", "Премиум модель", "photos/bike4.jpg"),
    ]

    cur.executemany(
        "INSERT INTO bikes (name, price, description, photo) VALUES (?, ?, ?, ?)",
        bikes
    )
    conn.commit()

seed()

# -------------------
# STATES
# -------------------

class RentForm(StatesGroup):
    name = State()
    phone = State()

class AdminAddBike(StatesGroup):
    name = State()
    price = State()
    desc = State()
    photo = State()

# -------------------
# KEYBOARDS
# -------------------

def main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚲 Велосипеды"), KeyboardButton(text="📞 Контакты")],
            [KeyboardButton(text="🛠 Админ")]
        ],
        resize_keyboard=True
    )


def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить", callback_data="admin_add")],
        [InlineKeyboardButton(text="📦 Заявки", callback_data="admin_orders")]
    ])


def bike_kb(bike_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚲 Арендовать", callback_data=f"rent_{bike_id}")]
    ])

# -------------------
# START
# -------------------

@dp.message(CommandStart())
async def start(m: Message):
    await m.answer("🚲 Меню", reply_markup=main_kb())
    await show_bikes(m)

# -------------------
# SHOW BIKES
# -------------------

async def show_bikes(message: Message):
    rows = cur.execute("SELECT * FROM bikes").fetchall()

    for b in rows:
        text = f"<b>{b[1]}</b>\n💰 {b[2]}\n📝 {b[3]}"

        try:
            photo = FSInputFile(b[4])
            await message.answer_photo(photo, caption=text, reply_markup=bike_kb(b[0]))
        except:
            await message.answer(text, reply_markup=bike_kb(b[0]))

# -------------------
# MENU
# -------------------

@dp.message(F.text == "📞 Контакты")
async def contacts(m: Message):
    await m.answer("📍 Jana Masaryka 326/36\n📞 +420774424014")


@dp.message(F.text == "🚲 Велосипеды")
async def bikes(m: Message):
    await show_bikes(m)


@dp.message(F.text == "🛠 Админ")
async def admin(m: Message):
    if m.from_user.id != ADMIN_ID:
        return
    await m.answer("🛠 Admin", reply_markup=admin_kb())

# -------------------
# RENT
# -------------------

@dp.callback_query(F.data.startswith("rent_"))
async def rent(c: CallbackQuery, state: FSMContext):

    bike_id = int(c.data.split("_")[1])
    bike = cur.execute("SELECT name FROM bikes WHERE id=?", (bike_id,)).fetchone()

    if not bike:
        return await c.answer("Not found")

    await state.update_data(bike=bike[0])

    await c.message.answer("Введите имя:")
    await state.set_state(RentForm.name)

    await c.answer()


@dp.message(RentForm.name)
async def name(m: Message, state: FSMContext):
    await state.update_data(name=m.text)
    await m.answer("Введите телефон:")
    await state.set_state(RentForm.phone)


@dp.message(RentForm.phone)
async def phone(m: Message, state: FSMContext):

    data = await state.get_data()

    cur.execute(
        "INSERT INTO requests (bike, name, phone, user_id) VALUES (?, ?, ?, ?)",
        (data["bike"], data["name"], m.text, m.from_user.id)
    )
    conn.commit()

    await bot.send_message(
        ADMIN_ID,
        f"🔥 НОВАЯ ЗАЯВКА\n🚲 {data['bike']}\n👤 {data['name']}\n📞 {m.text}"
    )

    await m.answer("✅ Принято")
    await state.clear()

# -------------------
# ADMIN ORDERS
# -------------------

@dp.message(F.text == "📦 Заявки")
async def orders(m: Message):

    if m.from_user.id != ADMIN_ID:
        return

    rows = cur.execute("SELECT * FROM requests WHERE status='new'").fetchall()

    if not rows:
        return await m.answer("Нет заявок")

    text = "📦 Заявки:\n\n"

    for r in rows:
        text += f"#{r[0]} | {r[1]} | {r[2]} | {r[3]}\n"

    await m.answer(text)

# -------------------
# ADD BIKE
# -------------------

@dp.message(F.text == "➕ Добавить велосипед")
async def add_start(m: Message, state: FSMContext):

    if m.from_user.id != ADMIN_ID:
        return

    await state.set_state(AdminAddBike.name)
    await m.answer("Название?")


@dp.message(AdminAddBike.name)
async def add_name(m: Message, state: FSMContext):
    await state.update_data(name=m.text)
    await m.answer("Цена?")
    await state.set_state(AdminAddBike.price)


@dp.message(AdminAddBike.price)
async def add_price(m: Message, state: FSMContext):
    await state.update_data(price=m.text)
    await m.answer("Описание?")
    await state.set_state(AdminAddBike.desc)


@dp.message(AdminAddBike.desc)
async def add_desc(m: Message, state: FSMContext):
    await state.update_data(desc=m.text)
    await m.answer("Фото?")
    await state.set_state(AdminAddBike.photo)


@dp.message(AdminAddBike.photo)
async def add_photo(m: Message, state: FSMContext):

    if not m.photo:
        return await m.answer("Нужно фото")

    data = await state.get_data()

    cur.execute(
        "INSERT INTO bikes (name, price, description, photo) VALUES (?, ?, ?, ?)",
        (data["name"], data["price"], data["desc"], m.photo[-1].file_id)
    )
    conn.commit()

    await m.answer("✅ Добавлено")
    await state.clear()

# -------------------
# RUN
# -------------------

async def main():
    print("BOT STARTED")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

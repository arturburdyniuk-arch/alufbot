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
    KeyboardButton
)

# -------------------
# ENV
# -------------------

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

logging.basicConfig(level=logging.INFO)

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


def seed_bikes():
    cur.execute("SELECT COUNT(*) FROM bikes")
    if cur.fetchone()[0] > 0:
        return

    bikes = [
        ("DUOTTS S26", "1760 Kč / неделя", "Мощный универсальный электровелосипед", "https://example.com/1.jpg"),
        ("DUOTTS C29", "1440 Kč / неделя", "Комфортный велосипед для города", "https://example.com/2.jpg"),
        ("DUOTTS C29K 2 Battery", "1490 Kč / неделя", "С двумя батареями", "https://example.com/3.jpg"),
        ("Onesport OT08 Pro", "1600 Kč / неделя", "Премиум модель", "https://example.com/4.jpg"),
    ]

    cur.executemany(
        "INSERT INTO bikes (name, price, description, photo) VALUES (?, ?, ?, ?)",
        bikes
    )
    conn.commit()


seed_bikes()

# -------------------
# STATES
# -------------------

class RentForm(StatesGroup):
    name = State()
    phone = State()

class AddBike(StatesGroup):
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


def bike_kb(bike_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚲 Арендовать", callback_data=f"rent_{bike_id}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"del_{bike_id}")]
    ])


def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить", callback_data="admin_add")],
        [InlineKeyboardButton(text="📦 Новые заявки", callback_data="admin_new_orders")],
        [InlineKeyboardButton(text="📋 Все заявки", callback_data="admin_all_orders")]
    ])

# -------------------
# START
# -------------------

@dp.message(CommandStart())
async def start(m: Message):
    await m.answer("🚲 Меню", reply_markup=main_kb())


# -------------------
# MENU
# -------------------

@dp.message(F.text == "📞 Контакты")
async def contacts(m: Message):
    await m.answer("📍 Jana Masaryka 326/36\n📞 +420774424014")


@dp.message(F.text == "🚲 Велосипеды")
async def bikes_list(m: Message):

    rows = cur.execute("SELECT * FROM bikes").fetchall()

    for b in rows:
        text = f"<b>{b[1]}</b>\n💰 {b[2]}\n📝 {b[3]}"

        await m.answer_photo(
            photo=b[4],
            caption=text,
            reply_markup=bike_kb(b[0])
        )


@dp.message(F.text == "🛠 Админ")
async def admin_panel(m: Message):

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

    await state.update_data(bike=bike[0])

    await c.message.answer("Имя?")
    await state.set_state(RentForm.name)

    await c.answer()


@dp.message(RentForm.name)
async def name(m: Message, state: FSMContext):
    await state.update_data(name=m.text)
    await m.answer("Телефон?")
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
# DELETE BIKE
# -------------------

@dp.callback_query(F.data.startswith("del_"))
async def delete_bike(c: CallbackQuery):

    if c.from_user.id != ADMIN_ID:
        return await c.answer("No access")

    bike_id = int(c.data.split("_")[1])

    cur.execute("DELETE FROM bikes WHERE id=?", (bike_id,))
    conn.commit()

    await c.message.answer("🗑 Удалено")
    await c.answer()


# -------------------
# ADMIN ORDERS
# -------------------

@dp.callback_query(F.data == "admin_new_orders")
async def new_orders(c: CallbackQuery):

    rows = cur.execute("SELECT * FROM requests WHERE status='new'").fetchall()

    if not rows:
        return await c.message.answer("Нет новых заявок")

    for r in rows:
        await c.message.answer(
            f"🚲 {r[1]}\n👤 {r[2]}\n📞 {r[3]}\n\nID:{r[0]}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Закрыть", callback_data=f"close_{r[0]}")]
            ])
        )

    await c.answer()


@dp.callback_query(F.data.startswith("close_"))
async def close_order(c: CallbackQuery):

    if c.from_user.id != ADMIN_ID:
        return await c.answer("No access")

    order_id = int(c.data.split("_")[1])

    cur.execute("UPDATE requests SET status='done' WHERE id=?", (order_id,))
    conn.commit()

    await c.message.answer("✅ Закрыто")
    await c.answer()


# -------------------
# ADD BIKE
# -------------------

@dp.callback_query(F.data == "admin_add")
async def add(c: CallbackQuery, state: FSMContext):

    if c.from_user.id != ADMIN_ID:
        return await c.answer()

    await c.message.answer("Название?")
    await state.set_state(AddBike.name)
    await c.answer()


@dp.message(AddBike.name)
async def add_name(m: Message, state: FSMContext):
    await state.update_data(name=m.text)
    await m.answer("Цена?")
    await state.set_state(AddBike.price)


@dp.message(AddBike.price)
async def add_price(m: Message, state: FSMContext):
    await state.update_data(price=m.text)
    await m.answer("Описание?")
    await state.set_state(AddBike.desc)


@dp.message(AddBike.desc)
async def add_desc(m: Message, state: FSMContext):
    await state.update_data(desc=m.text)
    await m.answer("Отправь фото (как фото в Telegram)")
    await state.set_state(AddBike.photo)


@dp.message(AddBike.photo)
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
    print("CRM V2 STARTED")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())    default=DefaultBotProperties(parse_mode=ParseMode.HTML)


dp = Dispatcher()

# -------------------
# DATABASE (SQLite CRM)
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


def get_bikes():
    return cur.execute("SELECT id, name, price, description, photo FROM bikes").fetchall()


def add_request(bike, name, phone, user_id):
    cur.execute(
        "INSERT INTO requests (bike, name, phone, user_id) VALUES (?, ?, ?, ?)",
        (bike, name, phone, user_id)
    )
    conn.commit()


def get_requests():
    return cur.execute("SELECT id, bike, name, phone, status FROM requests").fetchall()


# -------------------
# STATES
# -------------------

class RentForm(StatesGroup):
    name = State()
    phone = State()

class AddBike(StatesGroup):
    name = State()
    price = State()
    desc = State()
    photo = State()


# -------------------
# KEYBOARDS
# -------------------

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚲 Велосипеды"), KeyboardButton(text="📞 Контакты")],
            [KeyboardButton(text="🛠 Админ")]
        ],
        resize_keyboard=True
    )


def bike_kb(bike_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚲 Арендовать", callback_data=f"rent_{bike_id}")]
    ])


def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить", callback_data="admin_add")],
        [InlineKeyboardButton(text="📦 Заявки", callback_data="admin_orders")]
    ])


# -------------------
# START
# -------------------

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("🚲 Меню:", reply_markup=main_menu())


# -------------------
# MENU BUTTONS
# -------------------

@dp.message(F.text == "📞 Контакты")
async def contacts(message: Message):
    await message.answer(
        "📍 Jana Masaryka 326/36\n📞 +420774424014"
    )


@dp.message(F.text == "🚲 Велосипеды")
async def show_bikes(message: Message):

    bikes = get_bikes()

    if not bikes:
        await message.answer("Нет велосипедов")
        return

    for b in bikes:
        text = f"<b>{b[1]}</b>\n💰 {b[2]}\n📝 {b[3]}"

        try:
            photo = FSInputFile(b[4])
            await message.answer_photo(photo, caption=text, reply_markup=bike_kb(b[0]))
        except:
            await message.answer(text, reply_markup=bike_kb(b[0]))


@dp.message(F.text == "🛠 Админ")
async def admin_panel(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    await message.answer("🛠 Admin panel", reply_markup=admin_kb())


# -------------------
# RENT
# -------------------

@dp.callback_query(F.data.startswith("rent_"))
async def rent(call: CallbackQuery, state: FSMContext):

    bike_id = int(call.data.split("_")[1])
    bike = cur.execute("SELECT name FROM bikes WHERE id=?", (bike_id,)).fetchone()

    if not bike:
        return await call.answer("Not found")

    await state.update_data(bike=bike[0])

    await call.message.answer("Введите имя:")
    await state.set_state(RentForm.name)

    await call.answer()


@dp.message(RentForm.name)
async def get_name(m: Message, state: FSMContext):
    await state.update_data(name=m.text)
    await m.answer("Введите телефон:")
    await state.set_state(RentForm.phone)


@dp.message(RentForm.phone)
async def get_phone(m: Message, state: FSMContext):

    data = await state.get_data()

    add_request(data["bike"], data["name"], m.text, m.from_user.id)

    await bot.send_message(
        ADMIN_ID,
        f"🔥 Заявка\n🚲 {data['bike']}\n👤 {data['name']}\n📞 {m.text}"
    )

    await m.answer("✅ Принято")
    await state.clear()


# -------------------
# ADMIN ORDERS
# -------------------

@dp.callback_query(F.data == "admin_orders")
async def admin_orders(call: CallbackQuery):

    if call.from_user.id != ADMIN_ID:
        return await call.answer("No access")

    rows = get_requests()

    if not rows:
        return await call.message.answer("Нет заявок")

    text = "📦 Заявки:\n\n"

    for r in rows:
        text += f"#{r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]}\n"

    await call.message.answer(text)
    await call.answer()


# -------------------
# ADD BIKE
# -------------------

@dp.callback_query(F.data == "admin_add")
async def add_start(call: CallbackQuery, state: FSMContext):

    if call.from_user.id != ADMIN_ID:
        return await call.answer()

    await call.message.answer("Название?")
    await state.set_state(AddBike.name)
    await call.answer()


@dp.message(AddBike.name)
async def add_name(m: Message, state: FSMContext):
    await state.update_data(name=m.text)
    await m.answer("Цена?")
    await state.set_state(AddBike.price)


@dp.message(AddBike.price)
async def add_price(m: Message, state: FSMContext):
    await state.update_data(price=m.text)
    await m.answer("Описание?")
    await state.set_state(AddBike.desc)


@dp.message(AddBike.desc)
async def add_desc(m: Message, state: FSMContext):
    await state.update_data(desc=m.text)
    await m.answer("Фото отправь")
    await state.set_state(AddBike.photo)


@dp.message(AddBike.photo)
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
# MAIN
# -------------------

async def main():
    print("CRM BOT STARTED")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())# -------------------
# BOT
# -------------------

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

# -------------------
# DATABASE
# -------------------

bikes = [
    {
        "id": 1,
        "name": "DUOTTS S26",
        "price": "1760+ Kč / неделя",
        "description": "Мощный универсальный электровелосипед",
        "photo": "photos/bike1.jpg"
    },
    {
        "id": 2,
        "name": "DUOTTS C29",
        "price": "1440+ Kč / неделя",
        "description": "Комфортный велосипед для города",
        "photo": "photos/bike2.jpg"
    },
    {
        "id": 3,
        "name": "DUOTTS C29K 2 Battery",
        "price": "1490+ Kč / неделя",
        "description": "Комфортный велосипед для города с двумя батареями на борту",
        "photo": "photos/bike3.jpg"
    },
    {
        "id": 4,
        "name": "Onesport ot08pro",
        "price": "1600+ Kč / неделя",
        "description": "Премиум модель с широкими колесами и двумя батареями на борту",
        "photo": "photos/bike4.jpg"
    }
]

requests = []

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

def user_panel():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🚲 Велосипеды в наличии"),
                KeyboardButton(text="📞 Контакты")
            ]
        ],
        resize_keyboard=True
    )

def admin_panel():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🚲 Велосипеды в наличии"),
                KeyboardButton(text="📞 Контакты")
            ],
            [
                KeyboardButton(text="➕ Добавить велосипед"),
                KeyboardButton(text="📦 Заявки")
            ]
        ],
        resize_keyboard=True
    )

def bike_kb(bike_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚲 Арендовать", callback_data=f"rent_{bike_id}")]
    ])

# -------------------
# START
# -------------------

@dp.message(CommandStart())
async def start(message: Message):

    if message.from_user.id == ADMIN_ID:
        await message.answer("🛠 Admin panel", reply_markup=admin_panel())
    else:
        await message.answer("🚲 Добро пожаловать!", reply_markup=user_panel())

    await show_bikes(message)

# -------------------
# SHOW BIKES
# -------------------

async def show_bikes(message: Message):

    for bike in bikes:
        text = (
            f"<b>{bike['name']}</b>\n\n"
            f"💰 {bike['price']}\n"
            f"📝 {bike['description']}"
        )

        try:
            photo = FSInputFile(bike["photo"])
            await message.answer_photo(photo, caption=text, reply_markup=bike_kb(bike["id"]))
        except:
            await message.answer(text, reply_markup=bike_kb(bike["id"]))

# -------------------
# CONTACTS
# -------------------

@dp.message(F.text == "📞 Контакты")
async def contacts(message: Message):
    await message.answer(
        "📍 Jana Masaryka 326/36\n"
        "📞 +420774424014"
    )

# -------------------
# BIKES BUTTON
# -------------------

@dp.message(F.text == "🚲 Велосипеды в наличии")
async def bikes_list(message: Message):
    await show_bikes(message)

# -------------------
# RENT FLOW
# -------------------

@dp.callback_query(F.data.startswith("rent_"))
async def rent(c: CallbackQuery, state: FSMContext):

    bike_id = int(c.data.split("_")[1])
    bike = next((b for b in bikes if b["id"] == bike_id), None)

    if not bike:
        return await c.answer("Not found")

    await state.update_data(bike=bike["name"])

    await c.message.answer("Введите имя:")
    await state.set_state(RentForm.name)

    await c.answer()

@dp.message(RentForm.name)
async def get_name(m: Message, state: FSMContext):
    await state.update_data(name=m.text)
    await m.answer("Введите телефон:")
    await state.set_state(RentForm.phone)

@dp.message(RentForm.phone)
async def get_phone(m: Message, state: FSMContext):

    data = await state.get_data()

    req = {
        "bike": data["bike"],
        "name": data["name"],
        "phone": m.text,
        "user_id": m.from_user.id
    }

    requests.append(req)

    await bot.send_message(
        ADMIN_ID,
        f"🔥 <b>Заявка</b>\n\n"
        f"🚲 {req['bike']}\n"
        f"👤 {req['name']}\n"
        f"📞 {req['phone']}"
    )

    await m.answer("✅ Заявка отправлена")
    await state.clear()

# -------------------
# ADMIN PANEL (TEXT BUTTONS)
# -------------------

@dp.message(F.text == "📦 Заявки")
async def admin_orders(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    if not requests:
        return await message.answer("Нет заявок")

    text = "📦 Заявки:\n\n"
    for r in requests:
        text += f"{r['bike']} | {r['name']} | {r['phone']}\n"

    await message.answer(text)

@dp.message(F.text == "➕ Добавить велосипед")
async def admin_add(message: Message, state: FSMContext):

    if message.from_user.id != ADMIN_ID:
        return

    await state.set_state(AdminAddBike.name)
    await message.answer("Название?")

@dp.message(AdminAddBike.name)
async def add_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AdminAddBike.price)
    await message.answer("Цена?")

@dp.message(AdminAddBike.price)
async def add_price(message: Message, state: FSMContext):
    await state.update_data(price=message.text)
    await state.set_state(AdminAddBike.desc)
    await message.answer("Описание?")

@dp.message(AdminAddBike.desc)
async def add_desc(message: Message, state: FSMContext):
    await state.update_data(desc=message.text)
    await state.set_state(AdminAddBike.photo)
    await message.answer("Отправь фото")

@dp.message(AdminAddBike.photo)
async def add_photo(message: Message, state: FSMContext):

    if not message.photo:
        return await message.answer("Нужно фото")

    data = await state.get_data()

    new_id = max([b["id"] for b in bikes]) + 1 if bikes else 1

    bikes.append({
        "id": new_id,
        "name": data["name"],
        "price": data["price"],
        "description": data["desc"],
        "photo": message.photo[-1].file_id
    })

    await message.answer("✅ Добавлено")
    await state.clear()

# -------------------
# MAIN
# -------------------

async def main():
    print("BOT STARTED")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())# -------------------

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

# -------------------
# DATABASE
# -------------------

bikes = [
    {
        "id": 1,
        "name": "DUOTTS S26",
        "price": "1760+ Kč / неделя",
        "description": "Мощный универсальный электровелосипед",
        "photo": "photos/bike1.jpg"
    },
    {
        "id": 2,
        "name": "DUOTTS C29",
        "price": "1440+ Kč / неделя",
        "description": "Комфортный велосипед для города",
        "photo": "photos/bike2.jpg"
    },
    {
        "id": 3,
        "name": "DUOTTS C29K 2 Battery",
        "price": "1490+ Kč / неделя",
        "description": "Комфортный велосипед для города с двумя батареями на борту",
        "photo": "photos/bike3.jpg"
    },
    {
        "id": 4,
        "name": "Onesport ot08pro",
        "price": "1600+ Kč / неделя",
        "description": "Премиум модель с широкими колесами и двумя батареями на борту",
        "photo": "photos/bike4.jpg"
    }
]

requests = []

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

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 Контакты", callback_data="contacts")]
    ])

def bike_kb(bike_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚲 Арендовать", callback_data=f"rent_{bike_id}")]
    ])

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить велосипед", callback_data="admin_add")],
        [InlineKeyboardButton(text="📦 Заявки", callback_data="admin_orders")]
    ])

# -------------------
# START
# -------------------

@dp.message(CommandStart())
async def start(message: Message):

    await message.answer("🚲 Доступные велосипеды:", reply_markup=main_menu())

    for bike in bikes:
        text = (
            f"<b>{bike['name']}</b>\n\n"
            f"💰 {bike['price']}\n"
            f"📝 {bike['description']}"
        )

        try:
            photo = FSInputFile(bike["photo"])
            await message.answer_photo(photo, caption=text, reply_markup=bike_kb(bike["id"]))
        except:
            await message.answer(text, reply_markup=bike_kb(bike["id"]))

# -------------------
# CONTACTS
# -------------------

@dp.callback_query(F.data == "contacts")
async def contacts(c: CallbackQuery):
    await c.message.answer(
        "📍 <b>Контакты</b>\n\n"
        "Jana Masaryka 326/36\n"
        "+420774424014"
    )
    await c.answer()

# -------------------
# RENT FLOW
# -------------------

@dp.callback_query(F.data.startswith("rent_"))
async def rent(c: CallbackQuery, state: FSMContext):

    bike_id = int(c.data.split("_")[1])
    bike = next((b for b in bikes if b["id"] == bike_id), None)

    if not bike:
        return await c.answer("Not found")

    await state.update_data(bike=bike["name"])

    await c.message.answer("Введите имя:")
    await state.set_state(RentForm.name)

    await c.answer()

@dp.message(RentForm.name)
async def get_name(m: Message, state: FSMContext):
    await state.update_data(name=m.text)
    await m.answer("Введите телефон:")
    await state.set_state(RentForm.phone)

@dp.message(RentForm.phone)
async def get_phone(m: Message, state: FSMContext):

    data = await state.get_data()

    req = {
        "bike": data["bike"],
        "name": data["name"],
        "phone": m.text,
        "user_id": m.from_user.id
    }

    requests.append(req)

    await bot.send_message(
        ADMIN_ID,
        f"🔥 <b>Заявка</b>\n\n"
        f"🚲 {req['bike']}\n"
        f"👤 {req['name']}\n"
        f"📞 {req['phone']}"
    )

    await m.answer("✅ Заявка отправлена")
    await state.clear()

# -------------------
# ADMIN PANEL
# -------------------

@dp.message(Command("admin"))
async def admin(m: Message):
    if m.from_user.id != ADMIN_ID:
        return

    await m.answer("🛠 Admin panel", reply_markup=admin_kb())

# -------------------
# ADMIN ORDERS
# -------------------

@dp.callback_query(F.data == "admin_orders")
async def admin_orders(c: CallbackQuery):

    if c.from_user.id != ADMIN_ID:
        return await c.answer("No access")

    if not requests:
        return await c.message.answer("Нет заявок")

    text = "📦 Заявки:\n\n"
    for r in requests:
        text += f"{r['bike']} | {r['name']} | {r['phone']}\n"

    await c.message.answer(text)
    await c.answer()

# -------------------
# ADD BIKE
# -------------------

@dp.callback_query(F.data == "admin_add")
async def admin_add(c: CallbackQuery, state: FSMContext):

    if c.from_user.id != ADMIN_ID:
        return await c.answer("No access")

    await c.message.answer("Название?")
    await state.set_state(AdminAddBike.name)

    await c.answer()

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
    await m.answer("Отправь фото")
    await state.set_state(AdminAddBike.photo)

@dp.message(AdminAddBike.photo)
async def add_photo(m: Message, state: FSMContext):

    if not m.photo:
        return await m.answer("Нужно фото")

    data = await state.get_data()

    new_id = max([b["id"] for b in bikes]) + 1 if bikes else 1

    bikes.append({
        "id": new_id,
        "name": data["name"],
        "price": data["price"],
        "description": data["desc"],
        "photo": m.photo[-1].file_id
    })

    await m.answer("✅ Добавлено")
    await state.clear()

# -------------------
# MAIN
# -------------------

async def main():
    print("BOT STARTED")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

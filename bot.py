import asyncio
import logging
import os

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
    FSInputFile,
    ReplyKeyboardMarkup,
    KeyboardButton
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

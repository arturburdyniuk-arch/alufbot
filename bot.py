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
    FSInputFile
)

# -------------------
# ENV
# -------------------

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

if not TOKEN:
    raise Exception("BOT_TOKEN missing")

# -------------------
# BOT
# -------------------

logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

# -------------------
# DATABASE (in-memory CRM)
# -------------------

bikes = [
    {
        "id": 1,
        "name": "DUOTTS S26",
        "price": "1760 Kč / week",
        "desc": "Power e-bike",
        "photo": "photos/bike1.jpg"
    }
]

requests = []  # CRM orders

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
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 Контакты", callback_data="contacts")]
    ])

def bike_kb(bike_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚲 Арендовать", callback_data=f"rent_{bike_id}")]
    ])

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить", callback_data="admin_add")],
        [InlineKeyboardButton(text="📋 Список", callback_data="admin_list")],
        [InlineKeyboardButton(text="📦 Заявки", callback_data="admin_orders")]
    ])

# -------------------
# START
# -------------------

@dp.message(CommandStart())
async def start(message: Message):

    await message.answer("🚲 Электровелосипеды:", reply_markup=main_kb())

    for b in bikes:
        text = f"<b>{b['name']}</b>\n💰 {b['price']}\n📝 {b['desc']}"

        try:
            photo = FSInputFile(b["photo"])
            await message.answer_photo(photo, caption=text, reply_markup=bike_kb(b["id"]))
        except:
            await message.answer(text, reply_markup=bike_kb(b["id"]))

# -------------------
# CONTACTS
# -------------------

@dp.callback_query(F.data == "contacts")
async def contacts(c: CallbackQuery):
    await c.message.answer(
        "📍 Jana Masaryka 326/36\n📞 +420774424014"
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
async def name(m: Message, state: FSMContext):
    await state.update_data(name=m.text)
    await m.answer("Введите телефон:")
    await state.set_state(RentForm.phone)

@dp.message(RentForm.phone)
async def phone(m: Message, state: FSMContext):

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
        f"🔥 Заявка\n🚲 {req['bike']}\n👤 {req['name']}\n📞 {req['phone']}"
    )

    await m.answer("✅ Принято!")
    await state.clear()

# -------------------
# ADMIN PANEL
# -------------------

@dp.message(Command("admin"))
async def admin(m: Message):

    if m.from_user.id != ADMIN_ID:
        return

    await m.answer("🛠 ADMIN PANEL", reply_markup=admin_kb())

# -------------------
# ADMIN CALLBACKS
# -------------------

@dp.callback_query(F.data == "admin_list")
async def admin_list(c: CallbackQuery):

    if c.from_user.id != ADMIN_ID:
        return await c.answer("No access")

    text = "🚲 Bikes:\n\n"
    for b in bikes:
        text += f"{b['id']}. {b['name']} - {b['price']}\n"

    await c.message.answer(text)
    await c.answer()

@dp.callback_query(F.data == "admin_orders")
async def admin_orders(c: CallbackQuery):

    if c.from_user.id != ADMIN_ID:
        return await c.answer("No access")

    if not requests:
        return await c.message.answer("Нет заявок")

    text = "📦 Orders:\n\n"
    for r in requests:
        text += f"🚲 {r['bike']} | {r['name']} | {r['phone']}\n"

    await c.message.answer(text)
    await c.answer()

# -------------------
# ADD BIKE
# -------------------

@dp.callback_query(F.data == "admin_add")
async def add_start(c: CallbackQuery, state: FSMContext):

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
    await m.answer("Отправь фото")
    await state.set_state(AddBike.photo)

@dp.message(AddBike.photo)
async def add_photo(m: Message, state: FSMContext):

    if not m.photo:
        return await m.answer("Нужно фото")

    data = await state.get_data()

    new_id = max([b["id"] for b in bikes]) + 1

    bikes.append({
        "id": new_id,
        "name": data["name"],
        "price": data["price"],
        "desc": data["desc"],
        "photo": m.photo[-1].file_id
    })

    await m.answer("✅ Добавлено")
    await state.clear()

# -------------------
# RUN
# -------------------

async def main():
    print("CRM BOT STARTED")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

# -------------------
# DATA
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
]

# -------------------
# STATES
# -------------------

class RentForm(StatesGroup):
    waiting_name = State()
    waiting_phone = State()

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

# -------------------
# START
# -------------------

@dp.message(CommandStart())
async def start(message: Message):

    await message.answer("🚲 Доступные электровелосипеды:", reply_markup=main_menu())

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
async def contacts(callback: CallbackQuery):
    await callback.message.answer(
        "📍 <b>Контакты</b>\n\n"
        "Jana Masaryka 326/36\n"
        "+420774424014"
    )
    await callback.answer()

# -------------------
# RENT
# -------------------

@dp.callback_query(F.data.startswith("rent_"))
async def rent(callback: CallbackQuery, state: FSMContext):

    bike_id = int(callback.data.split("_")[1])
    bike = next((b for b in bikes if b["id"] == bike_id), None)

    if not bike:
        return await callback.answer("Not found")

    await state.update_data(bike_name=bike["name"])

    await callback.message.answer("Введите ваше имя:")
    await state.set_state(RentForm.waiting_name)

    await callback.answer()

# -------------------
# FORM
# -------------------

@dp.message(RentForm.waiting_name)
async def name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)

    await message.answer("Введите телефон:")
    await state.set_state(RentForm.waiting_phone)

@dp.message(RentForm.waiting_phone)
async def phone(message: Message, state: FSMContext):

    await state.update_data(phone=message.text)
    data = await state.get_data()

    text = (
        "🔥 <b>Новая заявка</b>\n\n"
        f"🚲 {data['bike_name']}\n"
        f"👤 {data['name']}\n"
        f"📞 {data['phone']}\n"
        f"🆔 {message.from_user.id}"
    )

    await bot.send_message(ADMIN_ID, text)

    await message.answer("✅ Заявка отправлена")
    await state.clear()

# -------------------
# ADMIN PANEL
# -------------------

@dp.message(Command("admin"))
async def admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    await message.answer(
        "🛠 <b>Admin panel</b>\n\n"
        "Команды:\n"
        "/addbike — добавить велосипед"
    )

# -------------------
# ADD BIKE (simple flow)
# -------------------

@dp.message(Command("addbike"))
async def addbike(message: Message, state: FSMContext):

    if message.from_user.id != ADMIN_ID:
        return

    await state.set_state(AdminAddBike.name)
    await message.answer("Название велосипеда?")

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
    await message.answer("Отправь фото (как файл)")

@dp.message(AdminAddBike.photo)
async def add_photo(message: Message, state: FSMContext):

    data = await state.get_data()

    if not message.photo:
        return await message.answer("Отправь именно фото")

    file_id = message.photo[-1].file_id

    new_id = max(b["id"] for b in bikes) + 1

    bikes.append({
        "id": new_id,
        "name": data["name"],
        "price": data["price"],
        "description": data["desc"],
        "photo": file_id
    })

    await message.answer("✅ Велосипед добавлен")
    await state.clear()

# -------------------
# RUN
# -------------------

async def main():
    print("BOT STARTED")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

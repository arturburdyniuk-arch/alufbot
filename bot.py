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
        "price": "1760 Kč / week",
        "description": "Power e-bike",
        "photo": "photos/bike1.jpg"
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

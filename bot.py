import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)

from dotenv import load_dotenv

# -------------------
# ENV
# -------------------
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

print("BOT STARTING...")
print("TOKEN OK:", bool(TOKEN))
print("ADMIN OK:", bool(ADMIN_ID))

if not TOKEN:
    raise Exception("BOT_TOKEN is missing!")

if not ADMIN_ID:
    raise Exception("ADMIN_ID is missing!")

ADMIN_ID = int(ADMIN_ID)

# -------------------
# BOT INIT
# -------------------
logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# -------------------
# BIKE DATA
# -------------------
bikes = [
    {
        "id": 1,
        "name": "DUOTTS S26",
        "price": "1760+ Kč / неделя",
        "description": "Мощный универсальный электровелосипед",
        "photo": "https://via.placeholder.com/600x400?text=Bike+1"
    },
    {
        "id": 2,
        "name": "DUOTTS C29",
        "price": "1440+ Kč / неделя",
        "description": "Комфортный велосипед для города",
        "photo": "https://via.placeholder.com/600x400?text=Bike+2"
    },
    {
        "id": 3,
        "name": "DUOTTS C29K 2 Battery",
        "price": "1490+ Kč / неделя",
        "description": "С двумя батареями",
        "photo": "https://via.placeholder.com/600x400?text=Bike+3"
    },
    {
        "id": 4,
        "name": "Onesport OT08 Pro",
        "price": "1600+ Kč / неделя",
        "description": "Премиум модель",
        "photo": "https://via.placeholder.com/600x400?text=Bike+4"
    }
]

# -------------------
# STATES
# -------------------
class RentForm(StatesGroup):
    waiting_name = State()
    waiting_phone = State()

# -------------------
# START
# -------------------
@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("🚲 Доступные электровелосипеды:")

    for bike in bikes:
        text = (
            f"<b>{bike['name']}</b>\n\n"
            f"💰 {bike['price']}\n"
            f"📝 {bike['description']}"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="Оставить заявку",
                    callback_data=f"rent_{bike['id']}"
                )]
            ]
        )

        try:
            await message.answer_photo(
                photo=bike["photo"],
                caption=text,
                reply_markup=keyboard
            )
        except Exception as e:
            print("PHOTO ERROR:", e)
            await message.answer(text, reply_markup=keyboard)

# -------------------
# RENT
# -------------------
@dp.callback_query(F.data.startswith("rent_"))
async def rent_bike(callback: CallbackQuery, state: FSMContext):
    bike_id = int(callback.data.split("_")[1])
    bike = next((b for b in bikes if b["id"] == bike_id), None)

    if not bike:
        await callback.answer("Bike not found")
        return

    await state.update_data(bike_name=bike["name"])

    await callback.message.answer(
        f"Вы выбрали: <b>{bike['name']}</b>\n\nВведите ваше имя:"
    )

    await state.set_state(RentForm.waiting_name)
    await callback.answer()

# -------------------
# NAME
# -------------------
@dp.message(RentForm.waiting_name)
async def get_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)

    await message.answer("Введите ваш телефон:")
    await state.set_state(RentForm.waiting_phone)

# -------------------
# PHONE
# -------------------
@dp.message(RentForm.waiting_phone)
async def get_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)

    data = await state.get_data()

    text = (
        "🔥 <b>Новая заявка!</b>\n\n"
        f"🚲 Велосипед: {data['bike_name']}\n"
        f"👤 Имя: {data['name']}\n"
        f"📞 Телефон: {data['phone']}\n"
        f"🆔 ID: {message.from_user.id}"
    )

    try:
        await bot.send_message(ADMIN_ID, text)
    except Exception as e:
        print("ADMIN SEND ERROR:", e)

    await message.answer("✅ Заявка отправлена!")
    await state.clear()

# -------------------
# MAIN
# -------------------
async def main():
    try:
        print("START POLLING...")
        await dp.start_polling(bot)
    except Exception as e:
        print("CRASH:", e)

if __name__ == "__main__":
    asyncio.run(main())

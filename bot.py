import asyncio
import logging
import os

print("START")
print("TOKEN EXISTS:", bool(os.getenv("BOT_TOKEN")))
print("ADMIN EXISTS:", os.getenv("ADMIN_ID"))

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)

from dotenv import load_dotenv

# Загружаем .env
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Логирование
logging.basicConfig(level=logging.INFO)

# Создаем бота
bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()


# -------------------------
# ДАННЫЕ О ВЕЛОСИПЕДАХ
# -------------------------

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


# -------------------------
# СОСТОЯНИЯ
# -------------------------

class RentForm(StatesGroup):
    waiting_name = State()
    waiting_phone = State()


# -------------------------
# START
# -------------------------

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "🚲 Доступные электровелосипеды:"
    )

    # Отправляем все велосипеды
    for bike in bikes:

        text = (
            f"<b>{bike['name']}</b>\n\n"
            f"💰 {bike['price']}\n"
            f"📝 {bike['description']}"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Оставить заявку",
                        callback_data=f"rent_{bike['id']}"
                    )
                ]
            ]
        )

        photo = FSInputFile(bike["photo"])

        await message.answer_photo(
            photo=photo,
            caption=text,
            reply_markup=keyboard
        )


# -------------------------
# КНОПКА АРЕНДЫ
# -------------------------

@dp.callback_query(F.data.startswith("rent_"))
async def rent_bike(callback: CallbackQuery, state: FSMContext):

    bike_id = int(callback.data.split("_")[1])

    # Ищем велосипед
    bike = next(b for b in bikes if b["id"] == bike_id)

    # Сохраняем в state
    await state.update_data(bike_name=bike["name"])

    await callback.message.answer(
        f"Вы выбрали: <b>{bike['name']}</b>\n\n"
        "Введите ваше имя:"
    )

    await state.set_state(RentForm.waiting_name)

    await callback.answer()


# -------------------------
# ИМЯ
# -------------------------

@dp.message(RentForm.waiting_name)
async def get_name(message: Message, state: FSMContext):

    await state.update_data(name=message.text)

    await message.answer(
        "Введите ваш телефон:"
    )

    await state.set_state(RentForm.waiting_phone)


# -------------------------
# ТЕЛЕФОН
# -------------------------

@dp.message(RentForm.waiting_phone)
async def get_phone(message: Message, state: FSMContext):

    await state.update_data(phone=message.text)

    data = await state.get_data()

    # Сообщение админу
    admin_text = (
        "🔥 <b>Новая заявка!</b>\n\n"
        f"🚲 Велосипед: {data['bike_name']}\n"
        f"👤 Имя: {data['name']}\n"
        f"📞 Телефон: {data['phone']}\n\n"
        f"🆔 User ID: {message.from_user.id}"
    )

    # Отправляем вам
    await bot.send_message(
        ADMIN_ID,
        admin_text
    )

    await message.answer(
        "✅ Заявка отправлена!\n"
        "Мы скоро свяжемся с вами."
    )

    await state.clear()


# -------------------------
# ЗАПУСК
# -------------------------

async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

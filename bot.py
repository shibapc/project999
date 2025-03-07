from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from handlers.manual import register_manual_handlers
from handlers.ai import register_ai_handlers
import os
from config import BOT_TOKEN

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

user_data = {}

# Регистрация обработчиков
register_manual_handlers(dp, user_data)
register_ai_handlers(dp, user_data)

# Клавиатура для выбора метода
method_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
method_keyboard.add(KeyboardButton("Самостоятельно"), KeyboardButton("Искусственный Интеллект"))

@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    user_data[message.chat.id] = {
        "method": None,
        "current_handler": None
    }
    await message.answer("Как вы хотите создать смету?", reply_markup=method_keyboard)

@dp.message_handler(lambda message: message.chat.id in user_data and not user_data[message.chat.id].get('current_handler'))
async def handle_method_selection(message: types.Message):
    if message.text == "Самостоятельно":
        user_data[message.chat.id].update({
            "method": "manual",
            "current_handler": "manual",
            "sheets": [],
            "current_sheet": None,
            "products": {},
            "quantities": {},
            "step": None
        })
        await message.answer("Давай начнем создание сметы.\nСколько листов нужно создать (без учета СВОДНОГО)?", 
                           reply_markup=types.ReplyKeyboardRemove())
    
    elif message.text == "Искусственный Интеллект":
        user_data[message.chat.id].update({
            "method": "ai",
            "current_handler": "ai"
        })
        await message.answer("Функционал ИИ находится в разработке. Пока можете создать смету самостоятельно.", 
                           reply_markup=method_keyboard)
    
    else:
        await message.answer("Пожалуйста, выберите метод из предложенных кнопок.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
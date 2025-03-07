from aiogram import Dispatcher, types

def register_ai_handlers(dp: Dispatcher, user_data: dict):
    @dp.message_handler(
        lambda message: user_data.get(message.chat.id, {}).get('current_handler') == 'ai'
    )
    async def handle_ai_mode(message: types.Message):
        await message.answer("ИИ-режим в разработке. Используйте ручной режим через /start")
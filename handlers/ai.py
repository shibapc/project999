from telegram import Update
from telegram.ext import CallbackContext

async def handle_ai_mode(update: Update, context: CallbackContext, user_data: dict) -> int:
    """Обработка сообщений в ИИ-режиме."""
    chat_id = update.message.chat_id
    if user_data.get(chat_id, {}).get('current_handler') == 'ai':
        await update.message.reply_text(
            "ИИ-режим в разработке. Используйте ручной режим через /start"
        )
    return 9  # AI_STATEfrom telegram import Update
from telegram.ext import CallbackContext

async def handle_ai_mode(update: Update, context: CallbackContext, user_data: dict) -> int:
    """Обработка сообщений в ИИ-режиме."""
    chat_id = update.message.chat_id
    if user_data.get(chat_id, {}).get('current_handler') == 'ai':
        await update.message.reply_text(
            "ИИ-режим в разработке. Используйте ручной режим через /start"
        )
    return 9  # AI_STATE

def register_ai_handlers(application, user_data: dict):
    """Регистрация обработчиков для ИИ-режима."""
    # Обработчик уже зарегистрирован в ConversationHandler в bot.py, поэтому здесь ничего не добавляем
    pass

def register_ai_handlers(application, user_data: dict):
    """Регистрация обработчиков для ИИ-режима."""
    # Обработчик уже зарегистрирован в ConversationHandler в bot.py, поэтому здесь ничего не добавляем
    pass
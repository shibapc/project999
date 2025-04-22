import os
import sys
import logging
from utils.logger_config import setup_logging, log_user_state
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
    ConversationHandler,
    ContextTypes,
)
from handlers.manual import (
    get_number_of_sheets,
    get_sheet_names_and_quantities,
    get_maf_quantity,
    get_product_name,
    get_product_quantity,
    get_product_unit,
    process_next_product_or_sheet,
    go_back,
)
from handlers.ai import handle_ai_mode
from config import BOT_TOKEN
from utils.materials_manager import materials_manager
from utils.process_manager import process_manager

# Настройка логирования
setup_logging()
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Хранилище данных пользователей
user_data = {}

# Клавиатура для выбора метода
(
    METHOD_SELECTION,
    GET_SHEETS_NUM,
    GET_SHEET_NAMES,
    MAF_QUANTITY,
    PRODUCT_NAME,
    QUANTITY,
    PRICE,
    NEXT_PRODUCT,
    AI_STATE,
    CONFIRMATION_STATE,
) = range(10)


async def start_command(update: Update, context: CallbackContext) -> int:
    chat_id = update.message.chat_id
    logger.info(f"Пользователь {chat_id} запустил бота")

    # Очищаем кэш при новом старте
    materials_manager.clear_cache()

    user_data[chat_id] = {"products": {}, "current_handler": "manual"}
    log_user_state(logger, chat_id, user_data, "Инициализация нового пользователя")
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("Самостоятельно"), KeyboardButton("Через ИИ")]],
        resize_keyboard=True,
    )
    await update.message.reply_text(
        "Привет! Я помогу создать смету. Выбери способ создания:\n"
        "- Самостоятельно: ты вводишь данные поэтапно.\n"
        "- Через ИИ: просто напиши, что нужно, и я всё сделаю.",
        reply_markup=keyboard,
    )
    return METHOD_SELECTION


async def handle_method_selection(update: Update, context: CallbackContext) -> int:
    chat_id = update.message.chat_id
    text = update.message.text
    logger.info(f"Пользователь {chat_id} выбрал метод: {text}")

    if text == "Самостоятельно":
        logger.debug("Запуск ручного режима создания сметы")
        user_data[chat_id]["current_handler"] = "manual"
        await update.message.reply_text(
            "Сколько листов нужно создать?",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("/cancel")]], resize_keyboard=True
            ),
        )
        return GET_SHEETS_NUM
    elif text == "Через ИИ":
        logger.debug("Запуск режима ИИ")
        user_data[chat_id]["current_handler"] = "ai"
        await update.message.reply_text(
            "Опиши, что должно быть в смете (например, 'Скамейка из дерева и горка из стали').",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("Отмена создания")]], resize_keyboard=True
            ),
        )
        return AI_STATE
    else:
        logger.warning(f"Некорректный ввод: {text}, chat_id={chat_id}")
        await update.message.reply_text(
            "Пожалуйста, выбери 'Самостоятельно' или 'Через ИИ'.",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("Самостоятельно"), KeyboardButton("Через ИИ")]],
                resize_keyboard=True,
            ),
        )
        return METHOD_SELECTION


async def cancel(update: Update, context: CallbackContext) -> int:
    """Обработка команды /cancel."""
    chat_id = update.message.chat_id
    user_data[chat_id].clear()
    await update.message.reply_text("Создание сметы отменено.", reply_markup=None)
    return -1  # ConversationHandler.END


# Добавляем обработчик ошибок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик всех ошибок."""
    logger.error(
        f"Update {update} вызвал ошибку {context.error}", exc_info=context.error
    )

    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "Произошла ошибка. Пожалуйста, начните сначала с помощью /start"
            )
    except Exception as e:
        logger.error(f"Ошибка в обработчике ошибок: {e}")


def main():
    """Настройка и запуск бота."""
    # Проверка на единственный экземпляр
    if not process_manager.ensure_single_instance():
        sys.exit(1)

    # Настройка обработчиков сигналов
    process_manager.setup_signal_handlers()

    application = Application.builder().token(BOT_TOKEN).build()

    # Настройка ConversationHandler для управления состояниями
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        states={
            METHOD_SELECTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_method_selection)
            ],
            GET_SHEETS_NUM: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & filters.Regex(r"^\d+$"),
                    lambda update, context: get_number_of_sheets(
                        update, context, user_data
                    ),
                )
            ],
            GET_SHEET_NAMES: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lambda update, context: get_sheet_names_and_quantities(
                        update, context, user_data
                    ),
                )
            ],
            MAF_QUANTITY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & filters.Regex(r"^\d+$"),
                    lambda update, context: get_maf_quantity(
                        update, context, user_data
                    ),
                )
            ],
            PRODUCT_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lambda update, context: get_product_name(
                        update, context, user_data
                    ),
                )
            ],
            QUANTITY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lambda update, context: get_product_quantity(
                        update, context, user_data
                    ),
                )
            ],
            PRICE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lambda update, context: get_product_unit(
                        update, context, user_data
                    ),
                ),
                MessageHandler(
                    filters.TEXT & filters.Regex(r"^Назад$"),
                    lambda update, context: go_back(update, context, user_data),
                ),
            ],
            NEXT_PRODUCT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lambda update, context: process_next_product_or_sheet(
                        update, context, user_data
                    ),
                ),
                MessageHandler(
                    filters.TEXT & filters.Regex(r"^Назад$"),
                    lambda update, context: go_back(update, context, user_data),
                ),
            ],
            CONFIRMATION_STATE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lambda update, context: process_next_product_or_sheet(
                        update, context, user_data
                    ),
                )
            ],
            AI_STATE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lambda update, context: handle_ai_mode(update, context, user_data),
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Регистрация обработчика разговора
    application.add_handler(conv_handler)

    # Добавляем обработчик ошибок
    application.add_error_handler(error_handler)

    # Запуск бота
    try:
        logger.info("Бот запущен...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    finally:
        process_manager.cleanup()


if __name__ == "__main__":
    main()

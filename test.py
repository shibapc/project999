import unittest
import asyncio
from unittest.mock import AsyncMock
from telegram import Update, Message, Chat, User, MessageEntity
from telegram.ext import ConversationHandler, CommandHandler, MessageHandler, filters
from bot import start_command, user_data, handle_method_selection
from handlers.manual import (
    get_number_of_sheets,
    get_sheet_names_and_quantities,
    get_maf_quantity,
    get_product_name,
    get_product_quantity,
    get_product_unit,
    process_next_product_or_sheet,
)
import logging

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger("telegram").setLevel(logging.INFO)

class BotFlowTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Создаём замоканный Bot
        self.bot = AsyncMock()
        self.bot.send_message = AsyncMock()

        # Настраиваем ConversationHandler (синхронизировано с bot.py)
        self.conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", start_command)],
            states={
                0: [MessageHandler(filters.Text(["Самостоятельно", "Через ИИ"]), handle_method_selection)],  # METHOD_SELECTION
                1: [MessageHandler(filters.Regex(r"^\d+$"), 
                                  lambda update, context: get_number_of_sheets(update, context, user_data))],  # GET_SHEETS_NUM
                2: [MessageHandler(filters.TEXT & ~filters.COMMAND, 
                                  lambda update, context: get_sheet_names_and_quantities(update, context, user_data))],  # GET_SHEET_NAMES
                3: [MessageHandler(filters.Regex(r"^\d+$"), 
                                  lambda update, context: get_maf_quantity(update, context, user_data))],  # MAF_QUANTITY
                4: [MessageHandler(filters.TEXT & ~filters.COMMAND, 
                                  lambda update, context: get_product_name(update, context, user_data))],  # PRODUCT_NAME
                5: [MessageHandler(filters.Regex(r"^\d+$"), 
                                  lambda update, context: get_product_quantity(update, context, user_data))],  # QUANTITY
                6: [MessageHandler(filters.TEXT & ~filters.COMMAND, 
                                  lambda update, context: get_product_unit(update, context, user_data))],  # PRICE
                7: [MessageHandler(filters.TEXT & ~filters.COMMAND, 
                                  lambda update, context: process_next_product_or_sheet(update, context, user_data))],  # NEXT_PRODUCT
            },
            fallbacks=[],
        )

        # Очищаем user_data
        user_data.clear()

    async def test_tunnel_flow(self):
        """Эмулируем сценарий создания сметы для Тоннеля, выводим ответы бота."""
        chat_id = 123
        messages = [
            "/start",
            "Самостоятельно",
            "1",
            "площадка",
            "1",
            "Изделия",
            "Тоннель",
            "300",
            "1800",
            "Подтвердить",
        ]

        # Создаём контекст
        context = AsyncMock()
        context.bot = self.bot
        context.user_data = user_data.setdefault(chat_id, {})

        # Явно устанавливаем current_handler
        context.user_data['current_handler'] = 'manual'
        context.user_data['products'] = {}  # Инициализируем products, как в start_command

        # Замоканный application
        application = None

        # Переменная для отслеживания текущего состояния
        current_state = None

        for i, text in enumerate(messages):
            # Создаём фейковый Update
            message = Message(
                message_id=i + 1,
                date=None,
                chat=Chat(id=chat_id, type="private"),
                from_user=User(id=chat_id, first_name="Test_User", is_bot=False),
                text=text,
                entities=[MessageEntity(type=MessageEntity.BOT_COMMAND, offset=0, length=len(text))] if text.startswith("/") else [],
            )
            message._bot = self.bot
            update = Update(update_id=i + 1, message=message)

            # Выводим отправленное сообщение и текущее состояние
            print(f"> fein: {text}")
            print(f"> Current conversation state: {current_state}")

            # Находим подходящий обработчик
            handler = None
            check_result = None
            # Проверяем обработчики в зависимости от текущего состояния
            if current_state is None:
                handlers_to_check = self.conv_handler.entry_points + sum(self.conv_handler.states.values(), [])
            else:
                handlers_to_check = self.conv_handler.states.get(current_state, []) + self.conv_handler.entry_points

            for h in handlers_to_check:
                check_result = h.check_update(update)
                print(f"> Filter for handler {h.callback.__name__} in state {current_state}: {check_result}")
                if check_result is not None and check_result:  # Проверяем истинное значение
                    handler = h
                    break

            if handler:
                try:
                    # Вызываем обработчик и сохраняем возвращённое состояние
                    next_state = await handler.handle_update(update, application, check_result, context)
                    current_state = next_state  # Обновляем текущее состояние
                    print(f"> Handler: {handler.callback.__name__}")
                    print(f"> Next state returned: {next_state}")
                    print(f"> user_data: {context.user_data}")
                except Exception as e:
                    print(f"> Error in handler: {e}")
            else:
                print(f"> No handler found for update: {text}")

            # Получаем и выводим ответ бота
            if self.bot.send_message.called:
                args, kwargs = self.bot.send_message.call_args
                response_text = kwargs.get("text", args[0] if args else "Бот не ответил")
                print(f"> Расчет сметы:\n{response_text}\n")
                self.bot.send_message.reset_mock()

            # Небольшая задержка
            await asyncio.sleep(0.1)

if __name__ == '__main__':
    unittest.main()
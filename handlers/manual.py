from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import MessageHandler, filters, CallbackContext
from utils import create_excel
import os
import logging

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def get_number_of_sheets(update: Update, context: CallbackContext, user_data: dict) -> int:
    """Обработка ввода количества листов."""
    chat_id = update.message.chat_id
    if user_data.get(chat_id, {}).get('current_handler') != 'manual':
        await update.message.reply_text("Пожалуйста, начни с команды /start.")
        return 1  # GET_SHEETS_NUM

    if not update.message.text.isdigit():
        await update.message.reply_text("Пожалуйста, введи число.\nСколько листов нужно создать?")
        return 1  # GET_SHEETS_NUM

    num_sheets = int(update.message.text)
    if num_sheets < 1:
        await update.message.reply_text("Количество листов должно быть больше 0.")
        return 1  # GET_SHEETS_NUM

    user_data[chat_id]["sheet_count"] = num_sheets
    await update.message.reply_text(
        "Введи названия листов через запятую (например, Скамейка,Карусель):",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("/cancel")]], resize_keyboard=True)
    )
    user_data[chat_id]["previous_state"] = 1  # GET_SHEETS_NUM
    return 2  # GET_SHEET_NAMES

async def get_sheet_names_and_quantities(update: Update, context: CallbackContext, user_data: dict) -> int:
    """Обработка названий листов."""
    chat_id = update.message.chat_id
    if "," not in update.message.text:
        await update.message.reply_text("Пожалуйста, введи названия через запятую (например, Скамейка,Карусель).")
        return 2  # GET_SHEET_NAMES

    sheets = [sheet.strip() for sheet in update.message.text.split(",")]
    if len(sheets) != user_data[chat_id]["sheet_count"]:
        await update.message.reply_text(
            f"Ты указал {user_data[chat_id]['sheet_count']} листов, но ввёл {len(sheets)} названий. "
            "Попробуй снова."
        )
        return 2  # GET_SHEET_NAMES

    user_data[chat_id]["sheets"] = sheets
    user_data[chat_id]["quantities"] = {}
    user_data[chat_id]["current_sheet_index"] = 0
    await ask_maf_quantity(update, user_data)
    user_data[chat_id]["previous_state"] = 2  # GET_SHEET_NAMES
    return 3  # MAF_QUANTITY

async def ask_maf_quantity(update: Update, user_data: dict) -> None:
    """Запрос количества для следующего листа."""
    chat_id = update.message.chat_id
    sheets = user_data[chat_id]["sheets"]
    current_index = user_data[chat_id]["current_sheet_index"]
    next_sheet = sheets[current_index]
    await update.message.reply_text(
        f"Для листа '{next_sheet}' укажи количество:",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("/cancel")]], resize_keyboard=True)
    )

async def get_maf_quantity(update: Update, context: CallbackContext, user_data: dict) -> int:
    """Обработка количества для листа."""
    chat_id = update.message.chat_id
    if not update.message.text.isdigit():
        await update.message.reply_text("Пожалуйста, введи число.")
        await ask_maf_quantity(update, user_data)
        return 3  # MAF_QUANTITY

    maf_quantity = int(update.message.text)
    sheets = user_data[chat_id]["sheets"]
    current_index = user_data[chat_id]["current_sheet_index"]
    current_maf = sheets[current_index]
    user_data[chat_id]["quantities"][current_maf] = maf_quantity
    user_data[chat_id]["current_sheet_index"] += 1

    if user_data[chat_id]["current_sheet_index"] < len(sheets):
        await ask_maf_quantity(update, user_data)
        return 3  # MAF_QUANTITY
    else:
        user_data[chat_id]["current_sheet"] = sheets[0]
        user_data[chat_id]["current_sheet_index"] = 0
        await update.message.reply_text(
            f"Теперь заполним данные для листа '{sheets[0]}'.\nВведи название изделия:",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("/cancel")]], resize_keyboard=True)
        )
        user_data[chat_id]["previous_state"] = 3  # MAF_QUANTITY
        logger.debug(f"Переход к вводу изделий для листа {sheets[0]}")
        return 4  # PRODUCT_NAME

async def get_product_name(update: Update, context: CallbackContext, user_data: dict) -> int:
    """Обработка названия изделия."""
    chat_id = update.message.chat_id
    current_sheet = user_data[chat_id]["current_sheet"]
    product_name = update.message.text

    if current_sheet not in user_data[chat_id]["products"]:
        user_data[chat_id]["products"][current_sheet] = []

    user_data[chat_id]["products"][current_sheet].append({
        "name": product_name,
        "quantity": 0,
        "unit": "",
        "price_per_unit": 0
    })
    await update.message.reply_text(
        f"Для изделия '{product_name}' укажи количество:",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("/cancel")]], resize_keyboard=True)
    )
    user_data[chat_id]["previous_state"] = 4  # PRODUCT_NAME
    return 5  # QUANTITY

async def get_product_quantity(update: Update, context: CallbackContext, user_data: dict) -> int:
    """Обработка количества изделия."""
    chat_id = update.message.chat_id
    if not update.message.text.isdigit():
        await update.message.reply_text("Пожалуйста, введи число.")
        return 5  # QUANTITY

    quantity = int(update.message.text)
    current_sheet = user_data[chat_id]["current_sheet"]
    user_data[chat_id]["products"][current_sheet][-1]["quantity"] = quantity

    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("м"), KeyboardButton("м²")], [KeyboardButton("м³"), KeyboardButton("шт")]],
        resize_keyboard=True
    )
    await update.message.reply_text(
        "Выбери единицу измерения (нажми на кнопку):",
        reply_markup=keyboard
    )
    user_data[chat_id]["previous_state"] = 5  # QUANTITY
    return 6  # UNIT

async def get_product_unit(update: Update, context: CallbackContext, user_data: dict) -> int:
    """Обработка единицы измерения."""
    chat_id = update.message.chat_id
    unit = update.message.text
    current_sheet = user_data[chat_id]["current_sheet"]
    user_data[chat_id]["products"][current_sheet][-1]["unit"] = unit
    await update.message.reply_text(
        f"Для изделия '{user_data[chat_id]['products'][current_sheet][-1]['name']}' укажи цену за единицу:",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Назад"), KeyboardButton("/cancel")]], resize_keyboard=True)
    )
    user_data[chat_id]["previous_state"] = 6  # UNIT
    return 7  # PRICE

async def get_product_price(update: Update, context: CallbackContext, user_data: dict) -> int:
    """Обработка цены за единицу."""
    chat_id = update.message.chat_id
    text = update.message.text
    if not text.replace('.', '', 1).isdigit():
        await update.message.reply_text(
            "Пожалуйста, введи число (можно с десятичной точкой, например, 100.50)."
        )
        return 7  # PRICE

    price = float(text)
    current_sheet = user_data[chat_id]["current_sheet"]
    user_data[chat_id]["products"][current_sheet][-1]["price_per_unit"] = price
    await update.message.reply_text(
        f"Изделие сохранено! Что дальше?\n- Введи название следующего изделия.\n- Напиши 'далее', чтобы перейти к следующему листу.",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("далее"), KeyboardButton("Назад")], [KeyboardButton("/cancel")]],
            resize_keyboard=True
        )
    )
    user_data[chat_id]["previous_state"] = 7  # PRICE
    return 8  # NEXT_PRODUCT

async def process_next_product_or_sheet(update: Update, context: CallbackContext, user_data: dict) -> int:
    """Обработка следующего изделия или листа."""
    chat_id = update.message.chat_id
    text = update.message.text.lower()

    if text == 'далее':
        current_sheet = user_data[chat_id]["current_sheet"]
        sheets = user_data[chat_id]["sheets"]
        current_index = sheets.index(current_sheet)

        if current_index + 1 < len(sheets):
            next_sheet = sheets[current_index + 1]
            user_data[chat_id]["current_sheet"] = next_sheet
            await update.message.reply_text(
                f"Переходим к листу '{next_sheet}'.\nВведи название изделия:",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("/cancel")]], resize_keyboard=True)
            )
            user_data[chat_id]["previous_state"] = 8  # NEXT_PRODUCT
            return 4  # PRODUCT_NAME
        else:
            keyboard = ReplyKeyboardMarkup(
                [[KeyboardButton("Да"), KeyboardButton("Нет")]],
                resize_keyboard=True
            )
            await update.message.reply_text(
                "Закончить создание сметы и сформировать Excel-файл?",
                reply_markup=keyboard
            )
            user_data[chat_id]["awaiting_confirmation"] = True
            return 8  # NEXT_PRODUCT
    elif user_data[chat_id].get("awaiting_confirmation"):
        if text == "да":
            try:
                logger.debug(f"Попытка создать и отправить файл для chat_id={chat_id}")
                await update.message.reply_text("Формирую Excel-файл...")
                create_excel(chat_id, user_data)
                file_name = os.path.join("smeta_files", f"smeta_{chat_id}.xlsx")
                if os.path.exists(file_name):
                    with open(file_name, "rb") as file:
                        await update.message.reply_document(document=file)
                    logger.info(f"Файл {file_name} успешно отправлен")
                    os.remove(file_name)
                else:
                    logger.error(f"Файл {file_name} не найден после создания")
                    await update.message.reply_text("Ошибка: не удалось создать Excel-файл.")
                user_data[chat_id].clear()
                await update.message.reply_text(
                    "Смета создана! Начни заново с /start.",
                    reply_markup=None
                )
                return -1  # ConversationHandler.END
            except Exception as e:
                logger.error(f"Ошибка при создании/отправке файла: {str(e)}")
                await update.message.reply_text(f"Произошла ошибка: {str(e)}")
                user_data[chat_id].clear()
                return -1  # ConversationHandler.END
        elif text == "нет":
            user_data[chat_id]["awaiting_confirmation"] = False
            await update.message.reply_text(
                f"Продолжаем с листом '{user_data[chat_id]['current_sheet']}'.\nВведи название изделия:",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("/cancel")]], resize_keyboard=True)
            )
            return 4  # PRODUCT_NAME
        else:
            await update.message.reply_text(
                "Пожалуйста, выбери 'Да' или 'Нет'.",
                reply_markup=ReplyKeyboardMarkup(
                    [[KeyboardButton("Да"), KeyboardButton("Нет")]],
                    resize_keyboard=True
                )
            )
            return 8  # NEXT_PRODUCT
    else:
        current_sheet = user_data[chat_id]["current_sheet"]
        product_name = update.message.text
        user_data[chat_id]["products"][current_sheet].append({
            "name": product_name,
            "quantity": 0,
            "unit": "",
            "price_per_unit": 0
        })
        await update.message.reply_text(
            f"Для изделия '{product_name}' укажи количество:",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("/cancel")]], resize_keyboard=True)
        )
        user_data[chat_id]["previous_state"] = 8  # NEXT_PRODUCT
        return 5  # QUANTITY

async def go_back(update: Update, context: CallbackContext, user_data: dict) -> int:
    """Обработка кнопки 'Назад'."""
    chat_id = update.message.chat_id
    previous_state = user_data[chat_id].get("previous_state")

    if previous_state == 7:  # Назад с PRICE
        current_sheet = user_data[chat_id]["current_sheet"]
        await update.message.reply_text(
            "Выбери единицу измерения (нажми на кнопку):",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("м"), KeyboardButton("м²")], [KeyboardButton("м³"), KeyboardButton("шт")]],
                resize_keyboard=True
            )
        )
        return 6  # UNIT
    elif previous_state == 8:  # Назад с NEXT_PRODUCT
        current_sheet = user_data[chat_id]["current_sheet"]
        if user_data[chat_id]["products"][current_sheet]:
            user_data[chat_id]["products"][current_sheet].pop()  # Удаляем последнее изделие
        await update.message.reply_text(
            f"Для листа '{current_sheet}' укажи цену за единицу для '{user_data[chat_id]['products'][current_sheet][-1]['name']}':",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Назад"), KeyboardButton("/cancel")]], resize_keyboard=True)
        )
        return 7  # PRICE
    else:
        await update.message.reply_text("Нельзя вернуться назад на этом этапе.")
        return previous_state
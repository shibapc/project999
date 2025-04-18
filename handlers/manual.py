from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import CallbackContext
import json
import logging
from utils import create_excel
import os

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Загрузка базы материалов
with open("materials.json", "r", encoding="utf-8") as f:
    MATERIALS_DB = json.load(f)

def calculate_slide_cost(width_mm: float, height_mm: float) -> dict:
    """Рассчитать стоимость горки."""
    depth_mm = 300
    volume_m3 = (width_mm * height_mm * depth_mm) / 1_000_000_000
    cost_per_m3 = 700_000 - 50 * (height_mm - 900)
    wholesale_cost = volume_m3 * cost_per_m3
    return {
        "volume_m3": volume_m3,
        "cost_per_m3": cost_per_m3,
        "wholesale_cost": wholesale_cost,
        "retail_cost": wholesale_cost * 1.087
    }

def calculate_price_formula(formula: str, products: list) -> float:
    """Рассчитать стоимость по формуле."""
    sum_material_volume = sum(p.get("volume_m3", 0) * p["quantity"] for p in products if p["category"] == "Материалы")
    try:
        return eval(formula, {"__builtins__": {}}, {"sum_material_volume": sum_material_volume})
    except Exception as e:
        logger.error(f"Ошибка в формуле '{formula}': {e}")
        return 0.0

async def get_number_of_sheets(update: Update, context: CallbackContext, user_data: dict) -> int:
    """Обработка количества листов."""
    chat_id = update.message.chat_id
    text = update.message.text
    logger.debug(f"get_number_of_sheets: text='{text}', chat_id={chat_id}")
    if user_data.get(chat_id, {}).get("current_handler") != "manual":
        await update.message.reply_text("Начни с /start.")
        return 1
    if not text.isdigit() or int(text) < 1:
        await update.message.reply_text("Введи число больше 0.")
        return 1
    user_data[chat_id]["sheet_count"] = int(text)
    await update.message.reply_text(
        "Введи названия листов через запятую (например, Скамейка,Карусель):",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("/cancel")]], resize_keyboard=True)
    )
    return 2

async def get_sheet_names_and_quantities(update: Update, context: CallbackContext, user_data: dict) -> int:
    """Обработка названий листов."""
    chat_id = update.message.chat_id
    text = update.message.text.strip()
    logger.debug(f"get_sheet_names_and_quantities: text='{text}', chat_id={chat_id}")
    num_sheets = user_data[chat_id]["sheet_count"]
    sheets = [text] if num_sheets == 1 else [s.strip() for s in text.split(",")]
    if len(sheets) != num_sheets:
        await update.message.reply_text(f"Указано {num_sheets} листов, но ввёл {len(sheets)} названий.")
        return 2
    user_data[chat_id]["sheets"] = sheets
    user_data[chat_id]["quantities"] = {}
    user_data[chat_id]["current_sheet_index"] = 0
    await ask_maf_quantity(update, user_data)
    return 3

async def ask_maf_quantity(update: Update, user_data: dict):
    """Запрос количества для листа."""
    chat_id = update.message.chat_id
    sheet = user_data[chat_id]["sheets"][user_data[chat_id]["current_sheet_index"]]
    await update.message.reply_text(
        f"Для листа '{sheet}' укажи количество:",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("/cancel")]], resize_keyboard=True)
    )

async def get_maf_quantity(update: Update, context: CallbackContext, user_data: dict) -> int:
    """Обработка количества листа."""
    chat_id = update.message.chat_id
    text = update.message.text
    logger.debug(f"get_maf_quantity: text='{text}', chat_id={chat_id}")
    if not text.isdigit():
        await update.message.reply_text("Введи число.")
        await ask_maf_quantity(update, user_data)
        return 3
    maf_quantity = int(text)
    sheets = user_data[chat_id]["sheets"]
    current_index = user_data[chat_id]["current_sheet_index"]
    user_data[chat_id]["quantities"][sheets[current_index]] = maf_quantity
    user_data[chat_id]["current_sheet_index"] += 1
    if user_data[chat_id]["current_sheet_index"] < len(sheets):
        await ask_maf_quantity(update, user_data)
        return 3
    user_data[chat_id]["current_sheet"] = sheets[0]
    user_data[chat_id]["material_phase"] = True
    user_data[chat_id]["has_non_material"] = False
    await show_categories(update, user_data)
    return 4

async def show_categories(update: Update, user_data: dict):
    """Показать категории в зависимости от фазы."""
    chat_id = update.message.chat_id
    material_phase = user_data[chat_id]["material_phase"]
    categories = ["Материалы"] if material_phase else ["Работы", "Доставка"]
    keyboard = [[KeyboardButton(cat)] for cat in categories]
    if material_phase:
        keyboard.append([KeyboardButton("Завершить выбор материалов"), KeyboardButton("/cancel")])
    else:
        # Проверяем, является ли текущий лист последним
        sheets = user_data[chat_id]["sheets"]
        current_sheet = user_data[chat_id]["current_sheet"]
        current_index = sheets.index(current_sheet)
        if current_index + 1 < len(sheets):
            keyboard.append([KeyboardButton("Переход к следующему листу"), KeyboardButton("/cancel")])
        else:
            keyboard.append([KeyboardButton("Перейти к формированию сметы"), KeyboardButton("/cancel")])
    logger.debug(f"show_categories: material_phase={material_phase}, has_non_material={user_data[chat_id]['has_non_material']}, current_sheet={current_sheet}, sheets={sheets}, keyboard={keyboard}, chat_id={chat_id}")
    await update.message.reply_text(
        f"Для листа '{user_data[chat_id]['current_sheet']}' выбери категорию:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def get_product_name(update: Update, context: CallbackContext, user_data: dict) -> int:
    """Обработка выбора категории или элемента."""
    chat_id = update.message.chat_id
    text = update.message.text.strip()
    material_phase = user_data[chat_id]["material_phase"]
    logger.debug(f"get_product_name: text='{text}', material_phase={material_phase}, has_non_material={user_data[chat_id]['has_non_material']}, chat_id={chat_id}")

    if text == "Завершить выбор материалов" and material_phase:
        user_data[chat_id]["material_phase"] = False
        logger.debug(f"Завершение выбора материалов, переход к Работы/Доставка, chat_id={chat_id}")
        await show_categories(update, user_data)
        return 4

    if text in ["Материалы", "Работы", "Доставка"]:
        if (material_phase and text != "Материалы") or (not material_phase and text == "Материалы"):
            logger.debug(f"Недоступная категория '{text}', material_phase={material_phase}, chat_id={chat_id}")
            await update.message.reply_text("Недоступная категория.")
            await show_categories(update, user_data)
            return 4
        items = MATERIALS_DB["materials"] if text == "Материалы" else MATERIALS_DB["works"] if text == "Работы" else MATERIALS_DB["other"]
        keyboard = [[KeyboardButton(item["name"])] for item in items]
        keyboard.append([KeyboardButton("Завершить выбор материалов") if material_phase else KeyboardButton("/cancel")])
        logger.debug(f"Показ элементов для категории '{text}', keyboard={keyboard}, chat_id={chat_id}")
        await update.message.reply_text(
            f"Выбери элемент для '{user_data[chat_id]['current_sheet']}':",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return 4

    item = next((i for i in (MATERIALS_DB["materials"] if material_phase else MATERIALS_DB["works"] + MATERIALS_DB["other"]) if i["name"] == text), None)
    if not item:
        logger.debug(f"Элемент '{text}' не найден, chat_id={chat_id}")
        await show_categories(update, user_data)
        return 4

    current_sheet = user_data[chat_id]["current_sheet"]
    if current_sheet not in user_data[chat_id]["products"]:
        user_data[chat_id]["products"][current_sheet] = []

    product = {
        "id": item["id"],
        "name": item["name"],
        "category": item["category"],
        "quantity": 0,
        "unit": item["unit"],
        "price_per_unit": item.get("price", 0),
        "variable": item.get("variable", False)
    }
    if not material_phase and "price_formula" in item:
        product["price_per_unit"] = calculate_price_formula(item["price_formula"], user_data[chat_id]["products"][current_sheet])
        user_data[chat_id]["has_non_material"] = True
        logger.debug(f"Установлен has_non_material=True для элемента '{product['name']}' с формулой, chat_id={chat_id}")
    elif not material_phase:
        user_data[chat_id]["has_non_material"] = True
        logger.debug(f"Установлен has_non_material=True для элемента '{product['name']}' без формулы, chat_id={chat_id}")
    user_data[chat_id]["products"][current_sheet].append(product)
    logger.debug(f"Добавлен элемент '{product['name']}', category={product['category']}, products={user_data[chat_id]['products'][current_sheet]}, chat_id={chat_id}")

    if product["variable"]:
        await update.message.reply_text(
            f"Для '{item['name']}' укажи ширину (мм):",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("/cancel")]], resize_keyboard=True)
        )
        user_data[chat_id]["awaiting_width"] = True
        return 5
    await update.message.reply_text(
        f"Для '{item['name']}' укажи количество ({item['unit']}):",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("/cancel")]], resize_keyboard=True)
    )
    return 5

async def get_product_quantity(update: Update, context: CallbackContext, user_data: dict) -> int:
    """Обработка количества или параметров."""
    chat_id = update.message.chat_id
    text = update.message.text
    current_sheet = user_data[chat_id]["current_sheet"]
    product = user_data[chat_id]["products"][current_sheet][-1]
    logger.debug(f"get_product_quantity: text='{text}', product={product['name']}, variable={product['variable']}, chat_id={chat_id}")

    if user_data[chat_id].get("awaiting_width"):
        if not text.replace(".", "", 1).isdigit():
            await update.message.reply_text("Введи число.")
            return 5
        product["width"] = float(text)
        user_data[chat_id]["awaiting_width"] = False
        user_data[chat_id]["awaiting_height"] = True
        await update.message.reply_text(
            f"Для '{product['name']}' укажи высоту (мм):",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("/cancel")]], resize_keyboard=True)
        )
        return 5
    elif user_data[chat_id].get("awaiting_height"):
        if not text.replace(".", "", 1).isdigit():
            await update.message.reply_text("Введи число.")
            return 5
        product["height"] = float(text)
        user_data[chat_id]["awaiting_height"] = False
        cost_data = calculate_slide_cost(product["width"], product["height"])
        product["volume_m3"] = cost_data["volume_m3"]
        product["quantity"] = cost_data["volume_m3"]  # Автоматически устанавливаем quantity = volume_m3
        product["price_per_unit"] = cost_data["cost_per_m3"]
        logger.debug(f"Установлено quantity={product['quantity']} для '{product['name']}' на основе volume_m3={cost_data['volume_m3']}, chat_id={chat_id}")
        await update.message.reply_text(
            f"Для '{product['name']}' (ширина {product['width']} мм, высота {product['height']} мм):\n"
            f"Объём: {cost_data['volume_m3']:.6f} м³\n"
            f"Оптовая цена за м³: {cost_data['cost_per_m3']:,.2f} ₽\n"
            f"Общая оптовая: {cost_data['wholesale_cost']:,.2f} ₽\n"
            f"Розничная: {cost_data['retail_cost']:,.2f} ₽\n"
            f"Подтвердить или ввести цену?",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("Подтвердить"), KeyboardButton("Ввести цену")], [KeyboardButton("Назад"), KeyboardButton("/cancel")]],
                resize_keyboard=True
            )
        )
        return 6
    else:
        if not text.replace(".", "", 1).isdigit():
            await update.message.reply_text("Введи число.")
            return 5
        product["quantity"] = float(text)
        logger.debug(f"Установлено quantity={product['quantity']} для '{product['name']}', chat_id={chat_id}")
        if product["category"] in ["Работы", "Доставка"] and "price_formula" in [i for i in (MATERIALS_DB["works"] + MATERIALS_DB["other"]) if i["name"] == product["name"]][0]:
            product["price_per_unit"] = calculate_price_formula(
                [i for i in (MATERIALS_DB["works"] + MATERIALS_DB["other"]) if i["name"] == product["name"]][0]["price_formula"],
                user_data[chat_id]["products"][current_sheet]
            )
            user_data[chat_id]["has_non_material"] = True
            logger.debug(f"Пересчитана цена и установлен has_non_material=True для '{product['name']}', chat_id={chat_id}")
        await update.message.reply_text(
            f"Цена за единицу для '{product['name']}' ({product['unit']}): {product['price_per_unit']:.2f} ₽.\n"
            f"Подтвердить или ввести цену?",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("Подтвердить"), KeyboardButton("Ввести цену")], [KeyboardButton("Назад"), KeyboardButton("/cancel")]],
                resize_keyboard=True
            )
        )
        return 6

async def get_product_unit(update: Update, context: CallbackContext, user_data: dict) -> int:
    """Обработка цены."""
    chat_id = update.message.chat_id
    text = update.message.text.lower()
    current_sheet = user_data[chat_id]["current_sheet"]
    product = user_data[chat_id]["products"][current_sheet][-1]
    logger.debug(f"get_product_unit: text='{text}', current_sheet={current_sheet}, product={product['name']}, quantity={product['quantity']}, variable={product['variable']}, chat_id={chat_id}")

    if text == "подтвердить":
        if product["quantity"] <= 0:
            logger.error(f"Ошибка: quantity={product['quantity']} для '{product['name']}', chat_id={chat_id}")
            await update.message.reply_text("Количество должно быть больше 0. Укажи количество заново.")
            await update.message.reply_text(
                f"Для '{product['name']}' укажи количество ({product['unit']}):",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("/cancel")]], resize_keyboard=True)
            )
            return 5
        if product["category"] in ["Работы", "Доставка"]:
            user_data[chat_id]["has_non_material"] = True
            logger.debug(f"Подтверждён элемент '{product['name']}', has_non_material=True, chat_id={chat_id}")
        await update.message.reply_text(f"Элемент '{product['name']}' сохранён! Что дальше?")
        await show_categories(update, user_data)
        return 4
    elif text == "ввести цену":
        logger.debug(f"Запрошен ввод цены для '{product['name']}', chat_id={chat_id}")
        await update.message.reply_text(
            f"Введи цену для '{product['name']}':",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Назад"), KeyboardButton("/cancel")]], resize_keyboard=True)
        )
        user_data[chat_id]["awaiting_price"] = True
        return 6
    elif user_data[chat_id].get("awaiting_price"):
        if not text.replace(".", "", 1).isdigit():
            await update.message.reply_text("Введи число.")
            return 6
        product["price_per_unit"] = float(text)
        user_data[chat_id]["awaiting_price"] = False
        if product["quantity"] <= 0:
            logger.error(f"Ошибка: quantity={product['quantity']} для '{product['name']}', chat_id={chat_id}")
            await update.message.reply_text("Количество должно быть больше 0. Укажи количество заново.")
            await update.message.reply_text(
                f"Для '{product['name']}' укажи количество ({product['unit']}):",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("/cancel")]], resize_keyboard=True)
            )
            return 5
        if product["category"] in ["Работы", "Доставка"]:
            user_data[chat_id]["has_non_material"] = True
            logger.debug(f"Подтверждён элемент '{product['name']}' с новой ценой, has_non_material=True, chat_id={chat_id}")
        await update.message.reply_text(f"Элемент '{product['name']}' сохранён! Что дальше?")
        await show_categories(update, user_data)
        return 4
    else:
        logger.debug(f"Некорректный ввод '{text}' в get_product_unit, chat_id={chat_id}")
        await update.message.reply_text(
            "Выбери 'Подтвердить' или 'Ввести цену'.",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("Подтвердить"), KeyboardButton("Ввести цену")], [KeyboardButton("Назад"), KeyboardButton("/cancel")]],
                resize_keyboard=True
            )
        )
        return 6

async def process_next_product_or_sheet(update: Update, context: CallbackContext, user_data: dict) -> int:
    """Обработка перехода к следующему листу или формированию сметы."""
    chat_id = update.message.chat_id
    text = update.message.text
    logger.debug(f"process_next_product_or_sheet: raw_text={repr(text)}, stripped_text='{text.strip()}', normalized_text='{text.strip().lower().replace('\\n', '').replace('\\r', '')}', bytes_text={text.encode('utf-8')}, user_data={user_data[chat_id]}, chat_id={chat_id}")

    # Проверяем, что user_data содержит необходимые ключи
    if not user_data.get(chat_id, {}).get("sheets") or not user_data[chat_id].get("current_sheet"):
        logger.error(f"Ошибка: sheets или current_sheet отсутствуют в user_data, chat_id={chat_id}")
        await update.message.reply_text("Ошибка в данных. Начни заново с /start.")
        user_data[chat_id].clear()
        return -1

    # Нормализуем текст для обработки
    normalized_text = text.strip().lower().replace('\n', '').replace('\r', '')
    if normalized_text == "переход к следующему листу":
        sheets = user_data[chat_id]["sheets"]
        current_sheet = user_data[chat_id]["current_sheet"]
        try:
            current_index = sheets.index(current_sheet)
        except ValueError:
            logger.error(f"Ошибка: current_sheet='{current_sheet}' не найден в sheets={sheets}, chat_id={chat_id}")
            await update.message.reply_text("Ошибка в данных. Начни заново с /start.")
            user_data[chat_id].clear()
            return -1

        logger.debug(f"Обработка 'Переход к следующему листу': current_sheet={current_sheet}, current_index={current_index}, sheets_count={len(sheets)}, products={user_data[chat_id]['products'].get(current_sheet, [])}, chat_id={chat_id}")
        if current_index + 1 < len(sheets):
            user_data[chat_id]["current_sheet"] = sheets[current_index + 1]
            user_data[chat_id]["material_phase"] = True
            user_data[chat_id]["has_non_material"] = False
            logger.debug(f"Переход к следующему листу: {user_data[chat_id]['current_sheet']}, chat_id={chat_id}")
            await show_categories(update, user_data)
            return 4
        else:
            logger.error(f"Ошибка: попытка перехода к следующему листу, но текущий лист последний, sheets={sheets}, chat_id={chat_id}")
            await update.message.reply_text("Это последний лист. Выберите 'Перейти к формированию сметы'.")
            await show_categories(update, user_data)
            return 4
    elif normalized_text == "перейти к формированию сметы":
        logger.debug(f"Обработка 'Перейти к формированию сметы', chat_id={chat_id}")
        await update.message.reply_text(
            "Закончить и создать Excel?",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Да"), KeyboardButton("Нет")]], resize_keyboard=True)
        )
        user_data[chat_id]["awaiting_confirmation"] = True
        return 8
    elif user_data[chat_id].get("awaiting_confirmation"):
        if text == "Да":
            await update.message.reply_text("Формирую Excel...")
            create_excel(chat_id, user_data)
            file_name = os.path.join("smeta_files", f"smeta_{chat_id}.xlsx")
            if os.path.exists(file_name):
                with open(file_name, "rb") as file:
                    await update.message.reply_document(document=file)
                os.remove(file_name)
            else:
                await update.message.reply_text("Ошибка создания файла.")
            user_data[chat_id].clear()
            await update.message.reply_text("Смета создана! Начни заново с /start.")
            return -1
        elif text == "Нет":
            user_data[chat_id]["awaiting_confirmation"] = False
            await show_categories(update, user_data)
            return 4
        await update.message.reply_text("Выбери 'Да' или 'Нет'.", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Да"), KeyboardButton("Нет")]]))
        return 8
    else:
        logger.debug(f"Необработанный ввод '{text}' в process_next_product_or_sheet, возвращаемся к категориям, chat_id={chat_id}")
        await show_categories(update, user_data)
        return 4

async def go_back(update: Update, context: CallbackContext, user_data: dict) -> int:
    """Обработка 'Назад'."""
    chat_id = update.message.chat_id
    current_sheet = user_data[chat_id]["current_sheet"]
    products = user_data[chat_id]["products"].get(current_sheet, [])
    logger.debug(f"go_back: current_sheet={current_sheet}, products_count={len(products)}, chat_id={chat_id}")
    if products:
        product = products[-1]
        if product.get("variable") and not product.get("height"):
            await update.message.reply_text(
                f"Для '{product['name']}' укажи высоту (мм):",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("/cancel")]], resize_keyboard=True)
            )
            user_data[chat_id]["awaiting_height"] = True
            return 5
        await update.message.reply_text(
            f"Для '{product['name']}' укажи количество ({product['unit']}):",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("/cancel")]], resize_keyboard=True)
        )
        return 5
    await show_categories(update, user_data)
    return 4
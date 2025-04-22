from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import CallbackContext
from utils.excel_creator import create_excel
from utils.number_formatter import format_number
from utils.materials_manager import materials_manager
import logging
import os
from calculations import (
    calculate_board_cost,
    calculate_steel_sheet_cost,
    calculate_slide_cost,
    calculate_tunnel_cost,
    calculate_concrete_wall_cost,
    calculate_price_formula,
    format_calculation_result,
)

# Настройка логирования
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Маппинг параметров
PARAM_MAP = {
    "длина": "length_mm",
    "ширина": "width_mm",
    "толщина": "thickness_mm",
    "высота": "height_mm",
    "радиус": "radius_mm",
    "углубление": "deepening_mm",
}

# Маппинг функций расчёта
CALC_FUNCTIONS = {
    "calculate_board_cost": calculate_board_cost,
    "calculate_steel_sheet_cost": calculate_steel_sheet_cost,
    "calculate_slide_cost": calculate_slide_cost,
    "calculate_tunnel_cost": calculate_tunnel_cost,
    "calculate_concrete_wall_cost": calculate_concrete_wall_cost,
}

async def validate_and_save_param(
    update: Update, user_data: dict, product: dict, item: dict, param: str, text: str
) -> bool:
    """Валидация и сохранение параметра."""
    chat_id = update.message.chat_id
    if not text.replace(".", "", 1).isdigit():
        await update.message.reply_text(f"Введи число для {param}.")
        return False

    value = float(text)
    if param in ["длина", "ширина", "высота", "радиус", "углубление"] and not (1 <= value <= 100000):
        await update.message.reply_text("Доступны значения только от 1 до 100000.")
        return False

    product[PARAM_MAP.get(param, param)] = value
    return True

async def handle_param_input(
    update: Update, context: CallbackContext, user_data: dict, product: dict, item: dict
) -> int:
    """Обработка ввода параметров."""
    chat_id = update.message.chat_id
    text = update.message.text
    param = user_data[chat_id]["awaiting_param"]

    if not await validate_and_save_param(update, user_data, product, item, param, text):
        return 5

    current_param_index = item["parameters"].index(param)
    if current_param_index + 1 < len(item["parameters"]):
        next_param = item["parameters"][current_param_index + 1]
        user_data[chat_id]["awaiting_param"] = next_param
        await update.message.reply_text(
            f"Укажи {next_param} для '{product['name']}':",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("/cancel")]], resize_keyboard=True
            ),
        )
        return 5

    user_data[chat_id]["awaiting_param"] = None
    return 0  # Все параметры введены

async def calculate_product_cost(
    chat_id: int, product: dict, item: dict, quantity: float
) -> dict:
    """Выполнение расчёта стоимости."""
    if not item.get("calculation_function"):
        logger.warning(f"Нет функции расчёта для '{item['name']}', chat_id={chat_id}")
        return {"общая_стоимость": 0, "количество": quantity}

    calc_function = CALC_FUNCTIONS.get(item["calculation_function"])
    if not calc_function:
        logger.error(
            f"Неизвестная функция расчета '{item['calculation_function']}', chat_id={chat_id}"
        )
        raise ValueError(f"Неизвестная функция расчета: {item['calculation_function']}")

    params = {
        PARAM_MAP.get(p, p): product.get(PARAM_MAP.get(p, p), 0)
        for p in item.get("parameters", [])
    }
    if item["calculation_function"] != "calculate_slide_cost":
        params["quantity"] = quantity

    logger.debug(
        f"Вызов функции '{item['calculation_function']}' с параметрами: {params}, chat_id={chat_id}"
    )

    try:
        # Проверяем, ожидает ли функция параметр materials_db
        if item["calculation_function"] == "calculate_tunnel_cost":
            materials_db = {
                "materials": materials_manager.get_all_items("materials"),
                "works": materials_manager.get_all_items("works"),
                "other": materials_manager.get_all_items("other"),
                "templates": materials_manager.get_all_items("templates"),
            }
            return calc_function(**params, materials_db=materials_db)
        return calc_function(**params)
    except TypeError as e:
        logger.error(
            f"Ошибка вызова функции '{item['calculation_function']}': {e}, параметры: {params}, chat_id={chat_id}"
        )
        raise ValueError(f"Ошибка в параметрах функции расчёта: {e}")
    except Exception as e:
        logger.error(
            f"Ошибка при выполнении '{item['calculation_function']}': {e}, chat_id={chat_id}"
        )
        raise

async def get_product_quantity(
    update: Update, context: CallbackContext, user_data: dict
) -> int:
    """Обработка параметров или количества для продукта."""
    chat_id = update.message.chat_id
    text = update.message.text
    current_sheet = user_data[chat_id]["current_sheet"]
    product = user_data[chat_id]["products"][current_sheet][-1]
    logger.debug(
        f"get_product_quantity: text='{text}', product={product['name']}, chat_id={chat_id}"
    )

    # Поиск элемента
    item = materials_manager.get_item(product["name"], product["category"].lower())
    if not item:
        logger.error(f"Элемент '{product['name']}' не найден, chat_id={chat_id}")
        await update.message.reply_text("Ошибка. Начни заново с /start.")
        return -1

    # Обработка параметров
    if user_data[chat_id].get("awaiting_param"):
        next_state = await handle_param_input(update, context, user_data, product, item)
        if next_state:
            return next_state

        # После ввода всех параметров
        if product["category"] == "Изделия":
            quantity = 1.0
            product["quantity"] = quantity
        else:
            user_data[chat_id]["awaiting_quantity"] = True
            await update.message.reply_text(
                f"Укажи количество для '{product['name']}' ({product['unit']}):",
                reply_markup=ReplyKeyboardMarkup(
                    [[KeyboardButton("/cancel")]], resize_keyboard=True
                ),
            )
            return 5

    # Обработка Работ и Доставки
    if product["category"] in ["Работы", "Доставка"]:
        if not text.replace(".", "", 1).isdigit():
            await update.message.reply_text("Введи число.")
            return 5
        product["quantity"] = float(text)
        item_data = materials_manager.get_item(
            product["name"], product["category"].lower()
        )
        if item_data and "price_formula" in item_data:
            all_products = []
            for sheet_products in user_data[chat_id]["products"].values():
                all_products.extend(sheet_products)
            product["price_per_unit"] = calculate_price_formula(
                item_data["price_formula"], all_products
            )
        user_data[chat_id]["has_non_material"] = True
        await update.message.reply_text(
            f"Цена за единицу для '{product['name']}' ({product['unit']}): {product['price_per_unit']:.0f} ₽.\n"
            f"Подтвердить или ввести цену?",
            reply_markup=ReplyKeyboardMarkup(
                [
                    [KeyboardButton("Подтвердить"), KeyboardButton("Ввести цену")],
                    [KeyboardButton("Назад"), KeyboardButton("/cancel")],
                ],
                resize_keyboard=True,
            ),
        )
        return 6

    # Обработка количества для остальных категорий
    if user_data[chat_id].get("awaiting_quantity"):
        if not text.replace(".", "", 1).isdigit():
            await update.message.reply_text("Введи число.")
            return 5
        quantity = float(text)
        user_data[chat_id]["awaiting_quantity"] = False
        product["quantity"] = quantity

    # Расчёт стоимости (только для категорий, не являющихся "Работы" или "Доставка")
    if product["category"] not in ["Работы", "Доставка"]:
        try:
            cost_data = await calculate_product_cost(
                chat_id, product, item, product["quantity"]
            )
            product["quantity"] = cost_data.get("количество", product["quantity"])
            if item.get("calculation_function") == "calculate_slide_cost":
                product["price_per_unit"] = cost_data.get("розничная_стоимость", 0)
            else:
                product["price_per_unit"] = (
                    cost_data.get("общая_стоимость", 0) / product["quantity"]
                )

            product["total_cost"] = product["quantity"] * product["price_per_unit"]
            result_message, message = format_calculation_result(
                product, item, cost_data
            )

            # Выводим только детализированное сообщение для тоннеля и бетонной стены
            if item.get("calculation_function") in ["calculate_tunnel_cost", "calculate_concrete_wall_cost"]:
                await update.message.reply_text(
                    message + "Подтвердить или ввести цену?",
                    reply_markup=ReplyKeyboardMarkup(
                        [
                            [KeyboardButton("Подтвердить"), KeyboardButton("Ввести цену")],
                            [KeyboardButton("Назад"), KeyboardButton("/cancel")],
                        ],
                        resize_keyboard=True,
                    ),
                )
            else:
                await update.message.reply_text(result_message)
                await update.message.reply_text(
                    message + "Подтвердить или ввести цену?",
                    reply_markup=ReplyKeyboardMarkup(
                        [
                            [KeyboardButton("Подтвердить"), KeyboardButton("Ввести цену")],
                            [KeyboardButton("Назад"), KeyboardButton("/cancel")],
                        ],
                        resize_keyboard=True,
                    ),
                )
            return 6
        except Exception as e:
            logger.error(
                f"Ошибка при расчете '{product['name']}': {e}, chat_id={chat_id}"
            )
            await update.message.reply_text(f"Ошибка расчета: {str(e)}. Попробуй снова.")
            return 5

    await update.message.reply_text("Введи число.")
    return 5

async def get_number_of_sheets(
    update: Update, context: CallbackContext, user_data: dict
) -> int:
    """Обработка количества листов."""
    chat_id = update.message.chat_id
    text = update.message.text
    
    logger.info(f"Получение количества листов от пользователя {chat_id}: {text}")
    
    if user_data.get(chat_id, {}).get("current_handler") != "manual":
        await update.message.reply_text("Начни с /start.")
        return 1
    if not text.isdigit() or int(text) < 1:
        logger.warning(f"Некорректное количество листов: {text}")
        await update.message.reply_text("Введи число больше 0.")
        return 1
    user_data[chat_id]["sheet_count"] = int(text)
    await update.message.reply_text(
        "Введи названия листов через запятую (например, Скамейка,Карусель):",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("/cancel")]], resize_keyboard=True),
    )
    return 2

async def get_sheet_names_and_quantities(
    update: Update, context: CallbackContext, user_data: dict
) -> int:
    """Обработка названий листов."""
    chat_id = update.message.chat_id
    text = update.message.text.strip()

    logger.info(f"Получение названий листов от пользователя {chat_id}")
    logger.debug(f"Названия листов: {text}")

    num_sheets = user_data[chat_id]["sheet_count"]
    sheets = [text] if num_sheets == 1 else [s.strip() for s in text.split(",")]
    if len(sheets) != num_sheets:
        await update.message.reply_text(
            f"Указано {num_sheets} листов, но ввёл {len(sheets)} названий."
        )
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
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("/cancel")]], resize_keyboard=True
        ),
    )

async def get_maf_quantity(
    update: Update, context: CallbackContext, user_data: dict
) -> int:
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
    current_sheet = user_data[chat_id].get("current_sheet", "<не задан>")
    sheets = user_data[chat_id].get("sheets", [])
    material_phase = user_data[chat_id]["material_phase"]
    categories = ["Материалы", "Изделия"] if material_phase else ["Работы", "Доставка"]
    keyboard = [[KeyboardButton(cat)] for cat in categories]
    if material_phase:
        keyboard.append(
            [KeyboardButton("Завершить выбор материалов"), KeyboardButton("/cancel")]
        )
    else:
        sheets = user_data[chat_id]["sheets"]
        current_sheet = user_data[chat_id]["current_sheet"]
        current_index = sheets.index(current_sheet)
        if current_index + 1 < len(sheets):
            keyboard.append(
                [
                    KeyboardButton("Переход к следующему листу"),
                    KeyboardButton("/cancel"),
                ]
            )
        else:
            keyboard.append(
                [
                    KeyboardButton("Перейти к формированию сметы"),
                    KeyboardButton("/cancel"),
                ]
            )
    logger.debug(
        f"show_categories: material_phase={material_phase}, has_non_material={user_data[chat_id]['has_non_material']}, "
        f"current_sheet={current_sheet}, sheets={sheets}, keyboard={keyboard}, chat_id={chat_id}"
    )
    await update.message.reply_text(
        f"Для листа '{user_data[chat_id]['current_sheet']}' выбери категорию:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )

async def get_product_name(
    update: Update, context: CallbackContext, user_data: dict
) -> int:
    """Обработка выбора категории или элемента."""
    chat_id = update.message.chat_id
    text = update.message.text.strip()
    material_phase = user_data[chat_id]["material_phase"]
    logger.debug(
        f"get_product_name: text='{text}', material_phase={material_phase}, "
        f"has_non_material={user_data[chat_id]['has_non_material']}, chat_id={chat_id}"
    )
    logger.info(
        f"""
    Обработка выбора: 
    - Текст: {text}
    - Chat ID: {chat_id}
    - Material Phase: {material_phase}
    - Current Sheet: {user_data[chat_id].get('current_sheet')}
    - Awaiting Param: {user_data[chat_id].get('awaiting_param')}
    """
    )

    if not material_phase and text in [
        "Переход к следующему листу",
        "Перейти к формированию сметы",
    ]:
        return await process_next_product_or_sheet(update, context, user_data)

    if text == "Завершить выбор материалов" and material_phase:
        user_data[chat_id]["material_phase"] = False
        logger.debug(
            f"Завершение выбора материалов, переход к Работы/Доставка, chat_id={chat_id}"
        )
        await show_categories(update, user_data)
        return 4

    if text in ["Материалы", "Работы", "Доставка"]:
        if (material_phase and text != "Материалы") or (
            not material_phase and text == "Материалы"
        ):
            logger.debug(
                f"Недоступная категория '{text}', material_phase={material_phase}, chat_id={chat_id}"
            )
            await update.message.reply_text("Недоступная категория.")
            await show_categories(update, user_data)
            return 4
        items = (
            materials_manager.get_all_items("materials")
            if text == "Материалы"
            else (
                materials_manager.get_all_items("works")
                if text == "Работы"
                else materials_manager.get_all_items("other")
            )
        )
        keyboard = [[KeyboardButton(item["name"])] for item in items]
        keyboard.append(
            [
                (
                    KeyboardButton("Завершить выбор материалов")
                    if material_phase
                    else KeyboardButton("/cancel")
                )
            ]
        )
        logger.debug(
            f"Показ элементов для категории '{text}', keyboard={keyboard}, chat_id={chat_id}"
        )
        await update.message.reply_text(
            f"Выбери элемент для '{user_data[chat_id]['current_sheet']}':",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )
        return 4

    if text == "Изделия":
        try:
            templates = materials_manager.get_all_items("templates")
            if not templates:
                logger.warning("Секция templates пуста")
                await update.message.reply_text("Список изделий пуст")
                return 4
            keyboard = [[KeyboardButton(template["name"])] for template in templates]
            keyboard.append([KeyboardButton("/cancel")])
            markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            user_data[chat_id]["selecting_template"] = True
            await update.message.reply_text("Выбери изделие:", reply_markup=markup)
            return 4
        except Exception as e:
            logger.error(f"Ошибка при получении списка изделий: {e}")
            await update.message.reply_text("Произошла ошибка. Попробуйте снова.")
            return 4

    item = None
    if user_data[chat_id].get("selecting_template"):
        item = materials_manager.get_item(text, "templates")
        user_data[chat_id]["selecting_template"] = False
    else:
        if material_phase:
            item = materials_manager.get_item(text, "materials")
        else:
            item = materials_manager.get_item(
                text, "works"
            ) or materials_manager.get_item(text, "other")

    if not item:
        logger.error(f"Элемент '{text}' не найден, chat_id={chat_id}")
        await show_categories(update, user_data)
        return 4

    current_sheet = user_data[chat_id].get("current_sheet")
    if not current_sheet:
        logger.error(f"Не найден текущий лист для chat_id={chat_id}")
        await update.message.reply_text("Ошибка. Начни заново с /start")
        return -1

    if current_sheet not in user_data[chat_id]["products"]:
        user_data[chat_id]["products"][current_sheet] = []

    product = {
        "name": item["name"],
        "category": item.get("category", ""),
        "unit": item.get("unit", "шт"),
        "variable": item.get("variable", False),
        "parameters": item.get("parameters", []),
        "calculation_function": item.get("calculation_function", None),
    }

    user_data[chat_id]["products"][current_sheet].append(product)
    logger.info(f"Добавлен продукт: {product}")

    if product["variable"] and product["parameters"]:
        user_data[chat_id]["awaiting_param"] = product["parameters"][0]
        await update.message.reply_text(
            f"Укажи {product['parameters'][0]} для '{product['name']}':",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("/cancel")]], resize_keyboard=True
            ),
        )
        return 5
    else:
        await update.message.reply_text(
            f"Укажи количество для '{product['name']}' ({product['unit']}):",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("/cancel")]], resize_keyboard=True
            ),
        )
        return 6

async def get_product_unit(
    update: Update, context: CallbackContext, user_data: dict
) -> int:
    """Обработка цены."""
    chat_id = update.message.chat_id
    text = update.message.text.lower()
    current_sheet = user_data[chat_id]["current_sheet"]
    product = user_data[chat_id]["products"][current_sheet][-1]
    logger.debug(
        f"get_product_unit: text='{text}', current_sheet={current_sheet}, product={product['name']}, "
        f"quantity={product['quantity']}, variable={product['variable']}, chat_id={chat_id}"
    )

    if text == "подтвердить":
        if product["quantity"] <= 0:
            logger.error(
                f"Ошибка: quantity={product['quantity']} для '{product['name']}', chat_id={chat_id}"
            )
            await update.message.reply_text(
                "Количество должно быть больше 0. Укажи количество заново."
            )
            await update.message.reply_text(
                f"Укажи количество для '{product['name']}' ({product['unit']}):",
                reply_markup=ReplyKeyboardMarkup(
                    [[KeyboardButton("/cancel")]], resize_keyboard=True
                ),
            )
            return 5
        if product["category"] in ["Работы", "Доставка"]:
            user_data[chat_id]["has_non_material"] = True
            logger.debug(
                f"Подтверждён элемент '{product['name']}', has_non_material=True, chat_id={chat_id}"
            )
        await update.message.reply_text(
            f"Элемент '{product['name']}' сохранён! Что дальше?"
        )
        await show_categories(update, user_data)
        return 4
    elif text == "ввести цену":
        logger.debug(f"Запрошен ввод цены для '{product['name']}', chat_id={chat_id}")
        await update.message.reply_text(
            f"Введи цену для '{product['name']}':",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("Назад"), KeyboardButton("/cancel")]],
                resize_keyboard=True,
            ),
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
            logger.error(
                f"Ошибка: quantity={product['quantity']} для '{product['name']}', chat_id={chat_id}"
            )
            await update.message.reply_text(
                "Количество должно быть больше 0. Укажи количество заново."
            )
            await update.message.reply_text(
                f"Укажи количество для '{product['name']}' ({product['unit']}):",
                reply_markup=ReplyKeyboardMarkup(
                    [[KeyboardButton("/cancel")]], resize_keyboard=True
                ),
            )
            return 5
        if product["category"] in ["Работы", "Доставка"]:
            user_data[chat_id]["has_non_material"] = True
            logger.debug(
                f"Подтверждён элемент '{product['name']}' с новой ценой, has_non_material=True, chat_id={chat_id}"
            )
        await update.message.reply_text(
            f"Элемент '{product['name']}' сохранён! Что дальше?"
        )
        await show_categories(update, user_data)
        return 4
    else:
        logger.debug(
            f"Некорректный ввод '{text}' в get_product_unit, chat_id={chat_id}"
        )
        await update.message.reply_text(
            "Выбери 'Подтвердить' или 'Ввести цену'.",
            reply_markup=ReplyKeyboardMarkup(
                [
                    [KeyboardButton("Подтвердить"), KeyboardButton("Ввести цену")],
                    [KeyboardButton("Назад"), KeyboardButton("/cancel")],
                ],
                resize_keyboard=True,
            ),
        )
        return 6

async def process_next_product_or_sheet(
    update: Update, context: CallbackContext, user_data: dict
) -> int:
    """Обработка перехода к следующему листу или формированию сметы."""
    chat_id = update.message.chat_id
    text = update.message.text
    logger.debug(f"process_next_product_or_sheet: text='{text}', chat_id={chat_id}")
    sheets = user_data[chat_id]["sheets"]
    current_sheet = user_data[chat_id]["current_sheet"]
    current_index = sheets.index(current_sheet)

    if text == "Переход к следующему листу":
        if current_index + 1 < len(sheets):
            user_data[chat_id]["current_sheet"] = sheets[current_index + 1]
            user_data[chat_id]["material_phase"] = True
            await update.message.reply_text(
                f"Переходим к листу '{user_data[chat_id]['current_sheet']}'."
            )
            await show_categories(update, user_data)
            return 4
    elif text == "Перейти к формированию сметы":
        excel_file = create_excel(chat_id, user_data)
        if not excel_file:
            logger.error(f"Не удалось создать Excel-файл для chat_id={chat_id}")
            await update.message.reply_text(
                "Ошибка при создании сметы. Попробуй снова."
            )
            return -1
        await update.message.reply_text(
            document=open(excel_file, "rb"),
            caption="Вот твоя смета!",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("/start")]], resize_keyboard=True
            ),
        )
        os.remove(excel_file)
        return -1

    await update.message.reply_text("Некорректный выбор. Попробуй снова.")
    await show_categories(update, user_data)
    return 4

async def go_back(update: Update, context: CallbackContext, user_data: dict) -> int:
    """Обработка 'Назад'."""
    chat_id = update.message.chat_id
    current_sheet = user_data[chat_id]["current_sheet"]
    products = user_data[chat_id]["products"].get(current_sheet, [])
    logger.debug(
        f"go_back: current_sheet={current_sheet}, products_count={len(products)}, chat_id={chat_id}"
    )
    if products:
        product = products[-1]
        if product.get("variable") and not product.get("height"):
            await update.message.reply_text(
                f"Для '{product['name']}' укажи высоту (мм):",
                reply_markup=ReplyKeyboardMarkup(
                    [[KeyboardButton("/cancel")]], resize_keyboard=True
                ),
            )
            user_data[chat_id]["awaiting_height"] = True
            return 5
        await update.message.reply_text(
            f"Для '{product['name']}' укажи количество ({product['unit']}):",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("/cancel")]], resize_keyboard=True
            ),
        )
        return 5
    await show_categories(update, user_data)
    return 4
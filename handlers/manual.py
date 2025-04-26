from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import CallbackContext
from utils.excel_creator import create_excel
from utils.number_formatter import format_number
from utils.materials_manager import materials_manager
from calculations import calculate_product_cost
import logging
import os

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

async def validate_and_save_param(
    update: Update, user_data: dict, product: dict, item: dict, param: dict, text: str
) -> bool:
    """Валидация и сохранение параметра на основе JSON."""
    chat_id = update.message.chat_id
    param_name = param["name"]
    param_key = param["key"]
    param_type = param["type"]
    param_min = param["min"]
    param_max = param["max"]

    # Проверка типа
    try:
        if param_type == "float":
            if not text.replace(".", "", 1).isdigit():
                await update.message.reply_text(f"Введи число для {param_name}.")
                return False
            value = float(text)
        else:
            logger.error(f"Неизвестный тип параметра '{param_type}' для {param_name}")
            await update.message.reply_text(f"Ошибка: неизвестный тип параметра.")
            return False
    except ValueError:
        await update.message.reply_text(f"Введи корректное число для {param_name}.")
        return False

    # Проверка диапазона
    if not (param_min <= value <= param_max):
        await update.message.reply_text(
            f"Значение для {param_name} должно быть от {param_min} до {param_max}."
        )
        return False

    product[param_key] = value
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

    current_param_index = [p["name"] for p in item["parameters"]].index(param["name"])
    if current_param_index + 1 < len(item["parameters"]):
        next_param = item["parameters"][current_param_index + 1]
        user_data[chat_id]["awaiting_param"] = next_param
        await update.message.reply_text(
            next_param["prompt"],
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("/cancel")]], resize_keyboard=True
            ),
        )
        return 5

    user_data[chat_id]["awaiting_param"] = None
    return 0  # Все параметры введены

async def format_calculation_result(product: dict, item: dict, cost_data: dict) -> str:
    """Форматирование результатов расчета на основе деталей."""
    params_str = ", ".join(
        f"{p['name']}: {product.get(p['key'], 0)}"
        for p in item.get("parameters", [])
    )
    message = f"Для '{product['name']}' ({params_str}):\n"

    calc_type = item.get("calculation", {}).get("type", "base_price")
    details = cost_data.get("детали", {})

    if calc_type == "base_price":
        message += f"Общая стоимость: {cost_data.get('общая_стоимость', 0):.0f} ₽\n"
    elif calc_type == "volume":
        message += f"Объём: {details.get('объём_м3', 0):.3f} м³\n"
        message += f"Розничная стоимость: {cost_data.get('общая_стоимость', 0):.0f} ₽\n"
    elif calc_type == "complex":
        for key, value in details.items():
            if key.startswith("материал_") or key.startswith("работа_"):
                name = key.replace("материал_", "").replace("работа_", "")
                message += f"{name}: {value.get('количество', 0):.2f} {item.get('unit', 'шт')}, "
                message += f"стоимость: {value.get('стоимость', 0):.0f} ₽\n"
            elif key in ["объём_стены_м3", "объём_фундамента_м3", "общий_объём_бетона_м3", "площадь_опалубки_м2"]:
                message += f"{key}: {value:.3f} {key.split('_')[-1]}\n"
            elif key in ["масса_арматуры_кг"]:
                message += f"{key}: {value:.0f} кг\n"
        message += f"Общая стоимость: {cost_data.get('общая_стоимость', 0):.0f} ₽\n"
    elif calc_type == "price_formula":
        message += f"Общая стоимость: {cost_data.get('общая_стоимость', 0):.0f} ₽\n"

    return message

async def calculate_product_cost_wrapper(
    chat_id: int, user_data: dict, product: dict, item: dict, quantity: float
) -> dict:
    """Обертка для вызова calculate_product_cost."""
    params = {
        p["key"]: product.get(p["key"], 0)
        for p in item.get("parameters", [])
    }
    params["quantity"] = quantity

    if item.get("calculation", {}).get("type") == "price_formula":
        all_products = []
        for sheet_products in user_data[chat_id]["products"].values():
            all_products.extend(sheet_products)
        params["all_products"] = all_products

    try:
        return calculate_product_cost(item, params, quantity)
    except Exception as e:
        logger.error(f"Ошибка при расчете '{product['name']}': {e}, chat_id={chat_id}")
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
    section = materials_manager.get_category_key(product["category"])
    item = materials_manager.get_item(product["name"], section)
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
        try:
            cost_data = await calculate_product_cost_wrapper(
                chat_id, user_data, product, item, product["quantity"]
            )
            product["price_per_unit"] = cost_data["общая_стоимость"] / product["quantity"]
            product["total_cost"] = cost_data["общая_стоимость"]
            user_data[chat_id]["has_non_material"] = True
            message = await format_calculation_result(product, item, cost_data)
            await update.message.reply_text(
                f"{message}Цена за единицу: {product['price_per_unit']:.0f} ₽.\n"
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
        except Exception as e:
            logger.error(f"Ошибка при расчете: {e}, chat_id={chat_id}")
            await update.message.reply_text(f"Ошибка расчета: {str(e)}. Попробуй снова.")
            return 5

    # Обработка количества для остальных категорий
    if user_data[chat_id].get("awaiting_quantity"):
        if not text.replace(".", "", 1).isdigit():
            await update.message.reply_text("Введи число.")
            return 5
        quantity = float(text)
        user_data[chat_id]["awaiting_quantity"] = False
        product["quantity"] = quantity

    # Расчёт стоимости
    try:
        cost_data = await calculate_product_cost_wrapper(
            chat_id, user_data, product, item, product["quantity"]
        )
        product["price_per_unit"] = cost_data["общая_стоимость"] / product["quantity"]
        product["total_cost"] = cost_data["общая_стоимость"]
        product["объём_м3"] = cost_data["детали"].get("объём_м3", 0)
        message = await format_calculation_result(product, item, cost_data)
        await update.message.reply_text(
            f"{message}Подтвердить или ввести цену?",
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
        logger.error(f"Ошибка при расчете: {e}, chat_id={chat_id}")
        await update.message.reply_text(f"Ошибка расчета: {str(e)}. Попробуй снова.")
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
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("/cancel")]], resize_keyboard=True
        ),
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
    user_data[chat_id]["material_phase"] = "material"
    await show_categories(update, user_data)
    return 4

async def show_categories(update: Update, user_data: dict):
    """Показать категории в зависимости от фазы."""
    chat_id = update.message.chat_id
    current_sheet = user_data[chat_id].get("current_sheet", "<не задан>")
    sheets = user_data[chat_id].get("sheets", [])
    material_phase = user_data[chat_id]["material_phase"]
    categories = materials_manager.get_categories_by_phase(material_phase)
    keyboard = [[KeyboardButton(cat["name"])] for cat in categories]
    if material_phase == "material":
        keyboard.append(
            [KeyboardButton("Завершить выбор материалов"), KeyboardButton("/cancel")]
        )
    else:
        current_index = sheets.index(current_sheet)
        if current_index + 1 < len(sheets):
            keyboard.append([KeyboardButton("Переход к следующему листу")])
        else:
            keyboard.append(
                [KeyboardButton("Перейти к формированию сметы и созданию коммерческого предложения")]
            )
    logger.debug(
        f"show_categories: material_phase={material_phase}, current_sheet={current_sheet}, "
        f"sheets={sheets}, keyboard={keyboard}, chat_id={chat_id}"
    )
    await update.message.reply_text(
        f"Для листа '{current_sheet}' выбери категорию:",
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
        f"chat_id={chat_id}"
    )

    if material_phase != "material" and text in [
        "Переход к следующему листу",
        "Перейти к формированию сметы и созданию коммерческого предложения",
    ]:
        return await process_next_product_or_sheet(update, context, user_data)

    if text == "Завершить выбор материалов" and material_phase == "material":
        user_data[chat_id]["material_phase"] = "non_material"
        logger.debug(
            f"Завершение выбора материалов, переход к non_material, chat_id={chat_id}"
        )
        await show_categories(update, user_data)
        return 4

    # Проверка, является ли текст категорией
    category_key = materials_manager.get_category_key(text)
    if category_key:
        categories = materials_manager.get_categories_by_phase(material_phase)
        if not any(cat["name"] == text for cat in categories):
            logger.debug(
                f"Недоступная категория '{text}', material_phase={material_phase}, chat_id={chat_id}"
            )
            await update.message.reply_text("Недоступная категория.")
            await show_categories(update, user_data)
            return 4
        items = materials_manager.get_all_items(category_key)
        keyboard = [[KeyboardButton(item["name"])] for item in items]
        keyboard.append(
            [
                KeyboardButton("Завершить выбор материалов")
                if material_phase == "material"
                else KeyboardButton("/cancel")
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

    # Поиск элемента
    section = None
    for cat in materials_manager.get_categories_by_phase(material_phase):
        section = materials_manager.get_category_key(cat["name"])
        item = materials_manager.get_item(text, section)
        if item:
            break
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
        "category": item["category"],
        "unit": item["unit"],
        "variable": item.get("variable", False),
        "parameters": item.get("parameters", []),
    }
    user_data[chat_id]["products"][current_sheet].append(product)
    logger.info(f"Добавлен продукт: {product}")

    if product["variable"] and product["parameters"]:
        user_data[chat_id]["awaiting_param"] = product["parameters"][0]
        await update.message.reply_text(
            product["parameters"][0]["prompt"],
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
        return 5

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
        f"quantity={product['quantity']}, chat_id={chat_id}"
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
        product["total_cost"] = product["price_per_unit"] * product["quantity"]
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
            user_data[chat_id]["material_phase"] = "material"
            await update.message.reply_text(
                f"Переходим к листу '{user_data[chat_id]['current_sheet']}'."
            )
            await show_categories(update, user_data)
            return 4
    elif text == "Перейти к формированию сметы и созданию коммерческого предложения":
        excel_file = create_excel(chat_id, user_data)
        if not excel_file:
            logger.error(f"Не удалось создать Excel-файл для chat_id={chat_id}")
            await update.message.reply_text(
                "Ошибка при создании сметы. Попробуй снова."
            )
            return -1

        try:
            from utils.commercial_offer.creator import create_commercial_proposal_docx
            cp_file = create_commercial_proposal_docx(chat_id, user_data)
        except Exception as e:
            logger.error(f"Не удалось создать DOCX КП для chat_id={chat_id}: {str(e)}")
            await update.message.reply_text(
                "Ошибка при создании коммерческого предложения. Попробуй снова."
            )
            return -1

        await update.message.reply_document(
            document=open(excel_file, "rb"),
            caption="Вот твоя смета!",
        )
        await update.message.reply_document(
            document=open(cp_file, "rb"),
            caption="Вот твоё коммерческое предложение!",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("/start")]], resize_keyboard=True
            ),
        )

        os.remove(excel_file)
        os.remove(cp_file)
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
        if product.get("variable") and product["parameters"]:
            user_data[chat_id]["awaiting_param"] = product["parameters"][0]
            await update.message.reply_text(
                product["parameters"][0]["prompt"],
                reply_markup=ReplyKeyboardMarkup(
                    [[KeyboardButton("/cancel")]], resize_keyboard=True
                ),
            )
            return 5
        await update.message.reply_text(
            f"Укажи количество для '{product['name']}' ({product['unit']}):",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("/cancel")]], resize_keyboard=True
            ),
        )
        return 5
    await show_categories(update, user_data)
    return 4
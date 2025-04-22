import math
import logging
from utils.logger_config import setup_logging
from utils.number_formatter import format_number

logger = logging.getLogger(__name__)

# Маппинг параметров
PARAM_MAP = {
    "длина": "length_mm",
    "ширина": "width_mm",
    "толщина": "thickness_mm",
    "высота": "height_mm",
    "радиус": "radius_mm",
}

def calculate_board_cost(length_mm: float, width_mm: float, thickness_mm: float, quantity: float = 1) -> dict:
    """Рассчитать стоимость доски."""
    volume_m3 = (length_mm * width_mm * thickness_mm) / 1_000_000_000
    cost_per_m3 = 20_000
    total_cost = volume_m3 * cost_per_m3 * quantity
    return {
        "общая_стоимость": total_cost,
        "количество": quantity
    }

def calculate_steel_sheet_cost(length_mm: float, width_mm: float, thickness_mm: float, quantity: float = 1) -> dict:
    """Рассчитать стоимость листа нержавеющей стали."""
    volume_m3 = (length_mm * width_mm * thickness_mm) / 1_000_000_000
    cost_per_m3 = 1_500_000
    total_cost = volume_m3 * cost_per_m3 * quantity
    return {
        "общая_стоимость": total_cost,
        "количество": quantity
    }

def calculate_slide_cost(width_mm: float, height_mm: float) -> dict:
    """Рассчитать стоимость горки."""
    depth_mm = 300
    volume_m3 = (width_mm * height_mm * depth_mm) / 1_000_000_000
    cost_per_m3 = 700_000 - 50 * (height_mm - 900)
    wholesale_cost = volume_m3 * cost_per_m3
    return {
        "объём_м3": volume_m3,
        "стоимость_за_м3": cost_per_m3,
        "оптовая_стоимость": wholesale_cost,
        "розничная_стоимость": wholesale_cost * 1.087,
    }

def calculate_tunnel_cost(radius_mm: float, length_mm: float, materials_db: dict, quantity: float = 1) -> dict:
    """Рассчитать стоимость тоннеля из нержавеющей стали с учётом резки и сварки по окружности и длине."""
    logger.info(f"Расчет стоимости тоннеля: радиус={radius_mm}мм, длина={length_mm}мм")
    try:
        logger.debug("Начало расчета стоимости тоннеля")
        
        steel_sheet = next(
            (material for material in materials_db["materials"] if material["name"] == "Лист нержавеющей стали"),
            None
        )
        if not steel_sheet:
            logger.error("Лист нержавеющей стали не найден в базе данных.")
            raise ValueError("Лист нержавеющей стали не найден в базе данных.")

        sheet_width_mm = steel_sheet.get("width_mm")
        sheet_length_mm = steel_sheet.get("length_mm")
        sheet_price = steel_sheet.get("price")

        if sheet_width_mm is None or sheet_length_mm is None:
            logger.error("Параметры 'width_mm' и 'length_mm' отсутствуют.")
            raise ValueError(
                "Параметры 'width_mm' и 'length_mm' для материала 'Лист нержавеющей стали' не заданы. "
                "Убедитесь, что они указаны пользователем."
            )

        cutting_work = next(
            (work for work in materials_db["works"] if work["name"] == "Резка листа"),
            None
        )
        cutting_price = cutting_work["price"] if cutting_work else 0

        welding_work = next(
            (work for work in materials_db["works"] if work["name"] == "Сварка листов нержавеющей стали"),
            None
        )
        welding_price = welding_work["price"] if welding_work else 0

        circumference = 2 * math.pi * radius_mm

        # Сколько блоков нужно по длине тоннеля (вдоль ширины листа)
        sheets_needed_length = math.ceil(length_mm / sheet_width_mm)

        # Сколько листов нужно по окружности (вдоль длины листа)
        sheets_needed_circumference = math.ceil(circumference / sheet_length_mm)

        # Нужна ли резка по окружности
        needs_cutting_circ = (sheets_needed_circumference * sheet_length_mm) > circumference
        cuts_circ = sheets_needed_length if needs_cutting_circ else 0

        # Сварки по окружности — между листами
        welds_circ = (sheets_needed_circumference - 1) * sheets_needed_length if sheets_needed_circumference > 1 else 0

        # Нужна ли резка по длине тоннеля
        total_length_from_sheets = sheets_needed_length * sheet_width_mm
        needs_cutting_len = total_length_from_sheets > length_mm
        cuts_len = 1 if needs_cutting_len else 0

        # Сварки по длине — между блоками
        welds_len = sheets_needed_length - 1 if sheets_needed_length > 1 else 0

        # Общие значения
        total_cuts = (cuts_circ + cuts_len) * quantity
        total_welds = (welds_circ + welds_len) * quantity
        total_sheets = sheets_needed_length * sheets_needed_circumference * quantity

        # Стоимости
        total_sheet_cost = total_sheets * sheet_price
        total_cutting_cost = total_cuts * cutting_price
        total_welding_cost = total_welds * welding_price
        total_cost = total_sheet_cost + total_cutting_cost + total_welding_cost

        result = {
            "количество_листов": total_sheets,
            "количество_резок": total_cuts,
            "количество_сварок": total_welds,
            "стоимость_листов": total_sheet_cost,
            "стоимость_резки": total_cutting_cost,
            "стоимость_сварки": total_welding_cost,
            "общая_стоимость": total_cost,
            "радиус": radius_mm,
            "длина": length_mm
        }
        logger.debug(f"Результат расчета: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Ошибка при расчете стоимости тоннеля: {str(e)}", exc_info=True)
        raise

def calculate_price_formula(formula: str, products: list) -> float:
    """Рассчитать стоимость по формуле."""
    sum_material_volume = sum(
        p.get("объём_м3", 0) * p["количество"]
        for p in products
        if p["category"] == "Материалы"
    )
    try:
        return eval(
            formula, {"__builtins__": {}}, {"sum_material_volume": sum_material_volume}
        )
    except Exception as e:
        logger.error(f"Ошибка в формуле '{formula}': {e}")
        return 0.0

def format_calculation_result(product: dict, item: dict, cost_data: dict) -> tuple:
    """Формирует сообщения с результатами расчёта в зависимости от функции расчёта."""
    # Формируем строку с параметрами
    params_str = ", ".join(
        f"{p}: {product.get(PARAM_MAP.get(p, p), 0)}" for p in item.get("parameters", [])
    )
    
    # Определяем формат вывода в зависимости от функции расчёта
    calc_function = item.get("calculation_function", "")
    match calc_function:
        case "calculate_tunnel_cost":
            message = (
                f"Для '{product['name']}' ({params_str}):\n"
                f"Количество листов: {cost_data.get('количество_листов', 0)}\n"
                f"Стоимость материалов: {cost_data.get('стоимость_листов', 0):.0f} ₽\n"
                f"Стоимость резки: {cost_data.get('стоимость_резки', 0):.0f} ₽\n"
                f"Стоимость сварки: {cost_data.get('стоимость_сварки', 0):.0f} ₽\n"
                f"Общая стоимость: {cost_data.get('общая_стоимость', 0):.0f} ₽\n"
            )
            result_message = ""  # Не возвращаем краткое сообщение
        case "calculate_slide_cost":
            message = (
                f"Для '{product['name']}' ({params_str}):\n"
                f"Объём: {cost_data.get('объём_м3', 0):.3f} м³\n"
                f"Розничная стоимость: {cost_data.get('розничная_стоимость', 0):.0f} ₽\n"
            )
            result_message = (
                f"Название: {product['name']}\n"
                f"Количество: {format_number(product['quantity'])} {product['unit']}\n"
                f"Цена за единицу: {format_number(product['price_per_unit'])} ₽\n"
                f"Итого: {format_number(product['total_cost'])} ₽"
            )
        case "calculate_board_cost" | "calculate_steel_sheet_cost":
            message = (
                f"Для '{product['name']}' ({params_str}):\n"
                f"Общая стоимость: {cost_data.get('общая_стоимость', 0):.0f} ₽\n"
            )
            result_message = (
                f"Название: {product['name']}\n"
                f"Количество: {format_number(product['quantity'])} {product['unit']}\n"
                f"Цена за единицу: {format_number(product['price_per_unit'])} ₽\n"
                f"Итого: {format_number(product['total_cost'])} ₽"
            )
        case _:
            message = (
                f"Для '{product['name']}' ({params_str}):\n"
                f"Общая стоимость: {cost_data.get('общая_стоимость', 0):.0f} ₽\n"
            )
            result_message = (
                f"Название: {product['name']}\n"
                f"Количество: {format_number(product['quantity'])} {product['unit']}\n"
                f"Цена за единицу: {format_number(product['price_per_unit'])} ₽\n"
                f"Итого: {format_number(product['total_cost'])} ₽"
            )

    return result_message, message
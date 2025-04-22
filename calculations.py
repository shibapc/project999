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
    "углубление": "deepening_mm"
}

def calculate_board_cost(
    length_mm: float, width_mm: float, thickness_mm: float, quantity: float = 1
) -> dict:
    """Рассчитать стоимость доски."""
    volume_m3 = (length_mm * width_mm * thickness_mm) / 1_000_000_000
    cost_per_m3 = 20_000
    total_cost = volume_m3 * cost_per_m3 * quantity
    return {"общая_стоимость": total_cost, "количество": quantity}

def calculate_steel_sheet_cost(
    length_mm: float, width_mm: float, thickness_mm: float, quantity: float = 1
) -> dict:
    """Рассчитать стоимость листа нержавеющей стали."""
    volume_m3 = (length_mm * width_mm * thickness_mm) / 1_000_000_000
    cost_per_m3 = 1_500_000
    total_cost = volume_m3 * cost_per_m3 * quantity
    return {"общая_стоимость": total_cost, "количество": quantity}

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

def calculate_tunnel_cost(
    radius_mm: float, length_mm: float, materials_db: dict, quantity: float = 1
) -> dict:
    """Рассчитать стоимость тоннеля из нержавеющей стали с учётом резки и сварки."""
    logger.info(f"Расчет стоимости тоннеля: радиус={radius_mm}мм, длина={length_mm}мм")
    try:
        logger.debug("Начало расчета стоимости тоннеля")

        steel_sheet = next(
            (
                material
                for material in materials_db["materials"]
                if material["name"] == "Лист нержавеющей стали"
            ),
            None,
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
                "Параметры 'width_mm' и 'length_mm' для материала 'Лист нержавеющей стали' не заданы."
            )

        cutting_work = next(
            (work for work in materials_db["works"] if work["name"] == "Резка листа"),
            None,
        )
        cutting_price = cutting_work["price"] if cutting_work else 0

        welding_work = next(
            (
                work
                for work in materials_db["works"]
                if work["name"] == "Сварка листов нержавеющей стали"
            ),
            None,
        )
        welding_price = welding_work["price"] if welding_work else 0

        circumference = 2 * math.pi * radius_mm
        sheets_needed_length = math.ceil(length_mm / sheet_width_mm)
        sheets_needed_circumference = math.ceil(circumference / sheet_length_mm)

        needs_cutting_circ = (sheets_needed_circumference * sheet_length_mm) > circumference
        cuts_circ = sheets_needed_length if needs_cutting_circ else 0
        welds_circ = (
            (sheets_needed_circumference - 1) * sheets_needed_length
            if sheets_needed_circumference > 1
            else 0
        )

        total_length_from_sheets = sheets_needed_length * sheet_width_mm
        needs_cutting_len = total_length_from_sheets > length_mm
        cuts_len = 1 if needs_cutting_len else 0
        welds_len = sheets_needed_length - 1 if sheets_needed_length > 1 else 0

        total_cuts = (cuts_circ + cuts_len) * quantity
        total_welds = (welds_circ + welds_len) * quantity
        total_sheets = sheets_needed_length * sheets_needed_circumference * quantity

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
            "длина": length_mm,
        }
        logger.debug(f"Результат расчета: {result}")
        return result

    except Exception as e:
        logger.error(f"Ошибка при расчете стоимости тоннеля: {str(e)}", exc_info=True)
        raise

def calculate_concrete_wall_cost(
    length_mm: float, width_mm: float, height_mm: float, deepening_mm: float, quantity: float = 1
) -> dict:
    """Рассчитать стоимость бетонной стены с учётом фундамента, арматуры, опалубки и заливки."""
    logger.info(f"Расчет стоимости бетонной стены: длина={length_mm}мм, ширина={width_mm}мм, высота={height_mm}мм, углубление={deepening_mm}мм")
    try:
        logger.debug("Начало расчета стоимости бетонной стены")

        # Углубление: 150 мм + введённое пользователем значение
        total_deepening_mm = 150 + deepening_mm
        logger.debug(f"Итоговое углубление: {total_deepening_mm} мм")

        # Проверка на отрицательные или нулевые значения
        if any(param <= 0 for param in [length_mm, width_mm, height_mm, deepening_mm]):
            logger.error("Параметры должны быть больше 0")
            raise ValueError("Все параметры (длина, ширина, высота, углубление) должны быть больше 0")

        # Объём стены (включая углубление)
        wall_height_mm = height_mm + total_deepening_mm
        wall_volume_m3 = (length_mm * width_mm * wall_height_mm) / 1_000_000_000

        # Объём фундамента (100 мм толщина)
        foundation_thickness_mm = 100
        foundation_volume_m3 = (length_mm * width_mm * foundation_thickness_mm) / 1_000_000_000

        # Общий объём бетона
        total_concrete_volume_m3 = wall_volume_m3 + foundation_volume_m3

        # Стоимость бетона (100 руб/м³)
        concrete_price_per_m3 = 100
        concrete_cost = total_concrete_volume_m3 * concrete_price_per_m3

        # Арматура: 100 кг на 1 м³ стены (без фундамента)
        rebar_kg_per_m3 = 100
        rebar_weight_kg = wall_volume_m3 * rebar_kg_per_m3
        rebar_price_per_kg = 50
        rebar_cost = rebar_weight_kg * rebar_price_per_kg

        # Опалубка: площадь боковых поверхностей стены
        side_area_m2 = 2 * (length_mm * wall_height_mm + width_mm * wall_height_mm) / 1_000_000
        formwork_price_per_m2 = 50  # Предположительная цена за м²
        formwork_cost = side_area_m2 * formwork_price_per_m2

        # Заливка бетона: 100 руб/м³
        pouring_price_per_m3 = 100
        pouring_cost = total_concrete_volume_m3 * pouring_price_per_m3

        # Общая стоимость
        total_cost = concrete_cost + rebar_cost + formwork_cost + pouring_cost

        result = {
            "объём_стены_м3": wall_volume_m3,
            "объём_фундамента_м3": foundation_volume_m3,
            "общий_объём_бетона_м3": total_concrete_volume_m3,
            "стоимость_бетона": concrete_cost,
            "масса_арматуры_кг": rebar_weight_kg,
            "стоимость_арматуры": rebar_cost,
            "площадь_опалубки_м2": side_area_m2,
            "стоимость_опалубки": formwork_cost,
            "стоимость_заливки": pouring_cost,
            "общая_стоимость": total_cost,
            "длина": length_mm,
            "ширина": width_mm,
            "высота": height_mm,
            "углубление": total_deepening_mm
        }
        logger.debug(f"Результат расчета: {result}")
        return result

    except Exception as e:
        logger.error(f"Ошибка при расчете стоимости бетонной стены: {str(e)}", exc_info=True)
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
    params_str = ", ".join(
        f"{p}: {product.get(PARAM_MAP.get(p, p), 0)}"
        for p in item.get("parameters", [])
    )

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
            result_message = ""
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
        case "calculate_concrete_wall_cost":
            message = (
                f"Для '{product['name']}' ({params_str}):\n"
                f"Объём стены: {cost_data.get('объём_стены_м3', 0):.3f} м³\n"
                f"Объём фундамента: {cost_data.get('объём_фундамента_м3', 0):.3f} м³\n"
                f"Общий объём бетона: {cost_data.get('общий_объём_бетона_м3', 0):.3f} м³\n"
                f"Стоимость бетона: {cost_data.get('стоимость_бетона', 0):.0f} ₽\n"
                f"Масса арматуры: {cost_data.get('масса_арматуры_кг', 0):.0f} кг\n"
                f"Стоимость арматуры: {cost_data.get('стоимость_арматуры', 0):.0f} ₽\n"
                f"Площадь опалубки: {cost_data.get('площадь_опалубки_м2', 0):.2f} м²\n"
                f"Стоимость опалубки: {cost_data.get('стоимость_опалубки', 0):.0f} ₽\n"
                f"Стоимость заливки: {cost_data.get('стоимость_заливки', 0):.0f} ₽\n"
                f"Общая стоимость: {cost_data.get('общая_стоимость', 0):.0f} ₽\n"
            )
            result_message = ""
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
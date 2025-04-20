import math
import logging

logger = logging.getLogger(__name__)

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

def calculate_tunnel_cost(radius_mm: float, length_mm: float, materials_db: dict) -> dict:
    """Рассчитать стоимость тоннеля из нержавеющей стали."""
    steel_sheet = next(
        (material for material in materials_db["materials"] if material["name"] == "Лист нержавеющей стали"),
        None
    )
    if not steel_sheet:
        raise ValueError("Лист нержавеющей стали не найден в базе данных.")

    sheet_width_mm = steel_sheet["parameters"]["width_mm"]
    sheet_length_mm = steel_sheet["parameters"]["length_mm"]
    sheet_price = steel_sheet["price"]

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
    sheets_needed_length = math.ceil(length_mm / sheet_width_mm)
    cuts_per_sheet = 1 if circumference < sheet_length_mm else 0
    extra_cut = 1 if length_mm % sheet_width_mm != 0 else 0
    total_cuts = (cuts_per_sheet * sheets_needed_length) + extra_cut
    welds_for_rounding = sheets_needed_length
    welds_for_joining = max(0, sheets_needed_length - 1)
    total_welds = welds_for_rounding + welds_for_joining

    total_sheet_cost = sheets_needed_length * sheet_price
    total_cutting_cost = total_cuts * cutting_price
    total_welding_cost = total_welds * welding_price
    total_cost = total_sheet_cost + total_cutting_cost + total_welding_cost

    return {
        "количество_листов": sheets_needed_length,
        "количество_резок": total_cuts,
        "количество_сварок": total_welds,
        "стоимость_листов": total_sheet_cost,
        "стоимость_резки": total_cutting_cost,
        "стоимость_сварки": total_welding_cost,
        "общая_стоимость": total_cost,
    }

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
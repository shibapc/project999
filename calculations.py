import math
import logging
from typing import Dict, Any
from utils.materials_manager import materials_manager

logger = logging.getLogger(__name__)

def safe_eval(expr: str, variables: Dict[str, Any]) -> float:
    """Безопасное вычисление выражения с заданными переменными."""
    try:
        allowed_names = {
            "math": math,
            "min": min,
            "max": max,
            "abs": abs,
            "round": round,
            "ceil": math.ceil
        }
        return eval(expr, {"__builtins__": {}}, {**allowed_names, **variables})
    except Exception as e:
        logger.error(f"Ошибка в safe_eval для выражения '{expr}': {e}")
        raise ValueError(f"Ошибка в формуле: {e}")

def calculate_product_cost(item: Dict[str, Any], params: Dict[str, Any], quantity: float) -> Dict[str, Any]:
    """Расчёт стоимости продукта на основе JSON-описания."""
    calc_type = item.get("calculation", {}).get("type", "base_price")
    details = {}
    total_cost = 0.0

    try:
        # Подготовка переменных
        variables = params.copy()

        # Вычисление промежуточных формул, если есть
        if "formulas" in item.get("calculation", {}):
            for key, formula in item["calculation"]["formulas"].items():
                variables[key] = safe_eval(formula, variables)

        if calc_type == "base_price":
            base_price = item.get("base_price", 0)
            total_cost = base_price * quantity

        elif calc_type == "volume":
            volume_formula = item["calculation"].get("volume_formula", "0")
            cost_per_m3 = (
                safe_eval(item["calculation"]["cost_per_m3_formula"], variables)
                if "cost_per_m3_formula" in item["calculation"]
                else item["calculation"].get("cost_per_m3", 0)
            )
            logger.debug(f"Параметры для volume: {params}")
            volume = safe_eval(volume_formula, params)  # Используем params вместо variables
            details["объём_м3"] = volume
            total_cost = volume * cost_per_m3 * quantity
            if "retail_multiplier" in item["calculation"]:
                total_cost *= item["calculation"]["retail_multiplier"]

        elif calc_type == "complex":
            for mat in item["calculation"].get("materials", []):
                mat_item = materials_manager.get_item(mat["name"], materials_manager.get_category_key(mat.get("category", "Материалы")))
                if not mat_item:
                    raise ValueError(f"Материал '{mat['name']}' не найден")
                # Формирование параметров материала
                mat_params = {}
                # Используем параметры из mat["parameters"], если есть
                if "parameters" in mat:
                    for key, value in mat["parameters"].items():
                        mat_params[key] = safe_eval(value, variables) if isinstance(value, str) else value
                # Добавляем параметры из mat_item["parameters"]
                for param in mat_item.get("parameters", []):
                    key = param["key"]
                    if key not in mat_params:
                        mat_params[key] = variables.get(key, params.get(key, 0))
                logger.debug(f"Параметры для материала '{mat['name']}': {mat_params}")
                mat_quantity = (
                    safe_eval(mat["quantity_formula"], variables) if "quantity_formula" in mat else
                    mat.get("quantity_per_unit", 1)
                ) * quantity
                mat_cost_data = calculate_product_cost(mat_item, mat_params, mat_quantity)
                details[f"материал_{mat['name']}"] = {
                    "количество": mat_quantity,
                    "стоимость": mat_cost_data["общая_стоимость"],
                }
                total_cost += mat_cost_data["общая_стоимость"]

            for work in item["calculation"].get("works", []):
                work_item = materials_manager.get_item(work["name"], materials_manager.get_category_key(work.get("category", "Работы")))
                if not work_item:
                    raise ValueError(f"Работа '{work['name']}' не найдена")
                work_quantity = (
                    safe_eval(work["quantity_formula"], variables) if "quantity_formula" in work else
                    mat.get("quantity_per_unit", 1)
                ) * quantity
                work_cost_data = calculate_product_cost(work_item, {}, work_quantity)
                details[f"работа_{work['name']}"] = {
                    "количество": work_quantity,
                    "стоимость": work_cost_data["общая_стоимость"],
                }
                total_cost += work_cost_data["общая_стоимость"]

        elif calc_type == "price_formula":
            variables["sum_material_volume"] = sum(
                p.get("объём_м3", 0) for p in params.get("all_products", [])
            )
            total_cost = safe_eval(item["calculation"]["price_formula"], variables) * quantity

        else:
            raise ValueError(f"Неизвестный тип расчёта: {calc_type}")

        return {"общая_стоимость": total_cost, "детали": details}

    except Exception as e:
        logger.error(f"Ошибка при расчете стоимости '{item.get('name', 'Unknown')}': {e}")
        raise
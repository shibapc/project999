import json
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class MaterialsManager:
    def __init__(self, config_file: str = "materials.json"):
        self.db: Dict[str, Any] = {}
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.config_file = config_file
        self.required_keys = {
            "categories": ["name", "key", "phase"],
            "materials": ["id", "name", "category", "unit"],
            "templates": ["id", "name", "category", "unit"],
            "works": ["id", "name", "category", "unit"],
            "other": ["id", "name", "category", "unit"],
        }
        self.parameter_keys = ["name", "key", "type", "min", "max", "prompt"]
        self.calculation_keys = ["type"]
        self.load_materials()
        self.validate_db()

    def load_materials(self) -> None:
        """Загрузка базы материалов из файла."""
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                self.db = json.load(f)
            logger.info("База материалов успешно загружена")
        except Exception as e:
            logger.error(f"Ошибка при загрузке базы материалов: {e}")
            raise

    def validate_db(self) -> None:
        """Проверка базы материалов на наличие необходимых ключей."""
        for section, required in self.required_keys.items():
            if section not in self.db:
                raise KeyError(f"Отсутствует секция {section} в базе материалов")

            for item in self.db[section]:
                missing = [key for key in required if key not in item]
                if missing:
                    logger.warning(
                        f"В элементе {item.get('name', 'Unknown')} секции {section} "
                        f"отсутствуют ключи: {missing}"
                    )

                # Валидация параметров, если есть
                if "parameters" in item:
                    for param in item["parameters"]:
                        missing_param_keys = [
                            key for key in self.parameter_keys if key not in param
                        ]
                        if missing_param_keys:
                            logger.warning(
                                f"В параметре элемента {item.get('name', 'Unknown')} секции {section} "
                                f"отсутствуют ключи: {missing_param_keys}"
                            )

                # Валидация поля calculation, если есть
                if "calculation" in item:
                    missing_calc_keys = [
                        key for key in self.calculation_keys if key not in item["calculation"]
                    ]
                    if missing_calc_keys:
                        logger.warning(
                            f"В расчете элемента {item.get('name', 'Unknown')} секции {section} "
                            f"отсутствуют ключи: {missing_calc_keys}"
                        )
                    calc_type = item["calculation"].get("type")
                    if calc_type == "volume":
                        if not item["calculation"].get("volume_formula"):
                            logger.warning(
                                f"В расчете элемента {item.get('name', 'Unknown')} секции {section} "
                                f"отсутствует volume_formula для типа 'volume'"
                            )
                    elif calc_type == "complex":
                        if not item["calculation"].get("materials") and not item["calculation"].get("works"):
                            logger.warning(
                                f"В расчете элемента {item.get('name', 'Unknown')} секции {section} "
                                f"отсутствуют materials или works для типа 'complex'"
                            )
                    elif calc_type == "price_formula":
                        if not item["calculation"].get("price_formula") and not item.get("price_formula"):
                            logger.warning(
                                f"В расчете элемента {item.get('name', 'Unknown')} секции {section} "
                                f"отсутствует price_formula"
                            )
                    elif calc_type == "base_price":
                        if not item.get("base_price"):
                            logger.warning(
                                f"В расчете элемента {item.get('name', 'Unknown')} секции {section} "
                                f"отсутствует base_price"
                            )

    def get_item(self, name: str, section: str = None) -> Optional[Dict[str, Any]]:
        """Получение элемента из базы с использованием кэша."""
        try:
            cache_key = f"{section}:{name}" if section else name
            if cache_key in self.cache:
                logger.debug(f"Использован кэш для элемента {name}")
                return self.cache[cache_key]

            if section:
                if section not in self.db:
                    logger.warning(f"Секция {section} не найдена")
                    return None
                item = next(
                    (i for i in self.db[section] if i.get("name") == name), None
                )
                if item:
                    self.cache[cache_key] = item
                    logger.info(f"Найден элемент '{name}' в секции {section}")
                    return item
            else:
                for sec in self.db:
                    if sec == "categories":
                        continue
                    item = next(
                        (i for i in self.db[sec] if i.get("name") == name), None
                    )
                    if item:
                        self.cache[cache_key] = item
                        logger.info(f"Найден элемент '{name}' в секции {sec}")
                        return item

            logger.warning(f"Элемент '{name}' не найден")
            return None

        except Exception as e:
            logger.error(f"Ошибка при поиске элемента '{name}': {e}")
            return None

    def get_all_items(self, section: str = None) -> List[Dict[str, Any]]:
        """Получение всех элементов из указанной секции."""
        try:
            if section is None:
                all_items = []
                for sec in self.db:
                    if sec != "categories":
                        all_items.extend(self.db[sec])
                logger.debug(f"Получено {len(all_items)} элементов из всех секций")
                return all_items

            if section not in self.db:
                logger.warning(f"Секция {section} не найдена")
                return []

            items = self.db[section]
            logger.debug(f"Получено {len(items)} элементов из секции {section}")
            return items

        except Exception as e:
            logger.error(f"Ошибка при получении элементов из секции {section}: {e}")
            return []

    def get_category_key(self, category_name: str) -> Optional[str]:
        """Получение ключа категории по её имени."""
        category = next(
            (cat for cat in self.db.get("categories", []) if cat["name"] == category_name),
            None,
        )
        return category["key"] if category else None

    def get_categories_by_phase(self, phase: str) -> List[Dict[str, Any]]:
        """Получение категорий по фазе (material или non_material)."""
        return [
            cat for cat in self.db.get("categories", []) if cat["phase"] == phase
        ]

    def clear_cache(self) -> None:
        """Очистка кэша."""
        self.cache.clear()
        logger.debug("Кэш очищен")

# Создаем глобальный экземпляр
materials_manager = MaterialsManager()
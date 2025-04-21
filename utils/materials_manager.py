import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class MaterialsManager:
    def __init__(self):
        self.db: Dict[str, Any] = {}
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.required_keys = {
            'materials': ['id', 'name', 'category', 'unit', 'price'],
            'templates': ['id', 'name', 'category', 'unit', 'parameters', 'calculation_function'],
            'works': ['id', 'name', 'category', 'unit'],
            'other': ['id', 'name', 'category', 'unit']
        }
        self.load_materials()
        self.validate_db()

    def load_materials(self) -> None:
        """Загрузка базы материалов из файла."""
        try:
            with open("materials.json", "r", encoding="utf-8") as f:
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

    def get_item(self, name: str, category_type: str = None) -> Optional[Dict[str, Any]]:
        """Получение элемента из базы с использованием кэша."""
        try:
            # Приведение category_type к правильному формату
            if category_type:
                if category_type.lower() == "изделия":
                    category_type = "templates"
                elif category_type.lower() == "материалы":
                    category_type = "materials"
                elif category_type.lower() == "работы":
                    category_type = "works"
                elif category_type.lower() == "доставка":
                    category_type = "other"

            cache_key = f"{category_type}:{name}" if category_type else name
            
            if cache_key in self.cache:
                logger.debug(f"Использован кэш для элемента {name}")
                return self.cache[cache_key]

            if category_type and category_type in self.db:
                logger.debug(f"Поиск элемента '{name}' в секции {category_type}")
                item = next(
                    (i for i in self.db[category_type] if i.get("name") == name),
                    None
                )
                if item:
                    self.cache[cache_key] = item
                    logger.info(f"Найден элемент '{name}' в секции {category_type}")
                    return item
            
            logger.warning(f"Элемент '{name}' не найден в секции {category_type}")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при поиске элемента '{name}': {e}")
            return None

    def get_all_items(self, section: str = None) -> list:
        """Получение всех элементов из указанной секции."""
        try:
            if section is None:
                all_items = []
                for section_items in self.db.values():
                    all_items.extend(section_items)
                return all_items

            section_map = {
                "изделия": "templates",
                "материалы": "materials",
                "работы": "works",
                "доставка": "other"
            }
            
            actual_section = section_map.get(section.lower(), section.lower())
            
            if actual_section not in self.db:
                logger.warning(f"Секция {actual_section} не найдена в базе материалов")
                return []
                
            items = self.db[actual_section]
            logger.debug(f"Получено {len(items)} элементов из секции {actual_section}")
            return items
            
        except Exception as e:
            logger.error(f"Ошибка при получении элементов из секции {section}: {e}")
            return []

    def clear_cache(self) -> None:
        """Очистка кэша."""
        self.cache.clear()
        logger.debug("Кэш очищен")

# Создаем глобальный экземпляр
materials_manager = MaterialsManager()
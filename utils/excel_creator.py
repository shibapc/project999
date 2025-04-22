import os
import logging
from openpyxl import Workbook
from openpyxl.styles import Alignment
from utils.logger_config import setup_logging, log_user_state
from utils.number_formatter import format_number

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def create_excel(chat_id: int, user_data: dict) -> str:
    """Создаёт Excel-файл с данными сметы."""
    try:
        logger.info(f"Начало создания Excel-файла для chat_id={chat_id}")
        log_user_state(logger, chat_id, user_data, "Создание Excel")
        wb = Workbook()
        del wb['Sheet']  # Удаляем лист по умолчанию

        # Создаем лист для каждого изделия
        for sheet_name, products in user_data[chat_id]["products"].items():
            ws = wb.create_sheet(title=sheet_name)

            # Заголовки
            headers = ["Название", "Категория", "Количество", "Единица", "Цена за единицу (₽)", "Итоговая стоимость (₽)"]
            ws.append(headers)

            # Выравнивание
            alignment = Alignment(horizontal="center", vertical="center")

            # Заполнение данных
            for product in products:
                try:
                    # Преобразуем строки в числа
                    try:
                        quantity = float(product.get("quantity", 0))
                        price_per_unit = float(product.get("price_per_unit", 0))
                        total_cost = quantity * price_per_unit
                    except (ValueError, TypeError):
                        logger.error(f"Ошибка преобразования типов: {product}")
                        quantity = 0
                        price_per_unit = 0
                        total_cost = 0

                    # Данные о продукте
                    row = [
                        product.get("name", ""),  # Название
                        product.get("category", ""),  # Категория
                        format_number(quantity),  # Количество
                        product.get("unit", ""),  # Единица
                        format_number(price_per_unit),  # Цена за единицу
                        format_number(total_cost),  # Итоговая стоимость
                    ]
                    ws.append(row)

                    # Форматирование строки
                    for cell in ws[ws.max_row]:
                        cell.alignment = alignment

                except (ValueError, TypeError) as e:
                    logger.error(f"Ошибка при обработке продукта {product}: {str(e)}")
                    continue

            # Автоматическая ширина столбцов
            for col in ws.columns:
                max_length = 0
                column = col[0].column_letter
                for cell in col:
                    try:
                        if cell.value:
                            max_length = max(max_length, len(str(cell.value)))
                    except:
                        pass
                adjusted_width = max_length + 2
                ws.column_dimensions[column].width = adjusted_width

        # Сохранение файла
        smeta_dir = os.path.join(os.getcwd(), "smeta_files")
        os.makedirs(smeta_dir, exist_ok=True)
        file_name = os.path.join(smeta_dir, f"smeta_{chat_id}.xlsx")
        wb.save(file_name)
        logger.info(f"Excel файл {file_name} успешно создан")
        return file_name

    except Exception as e:
        logger.error(f"Ошибка при создании Excel: {str(e)}", exc_info=True)
        log_user_state(logger, chat_id, user_data, f"Ошибка Excel: {str(e)}")
        raise

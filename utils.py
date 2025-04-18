import os
import logging
from openpyxl import Workbook
from openpyxl.styles import Alignment

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def create_excel(chat_id: int, user_data: dict):
    """Создаёт Excel-файл с данными сметы."""
    try:
        logger.debug(f"Создание Excel для chat_id={chat_id}")
        wb = Workbook()
        alignment = Alignment(horizontal="center", vertical="center")

        # Создаем лист для каждого изделия
        for sheet_name, products in user_data[chat_id]["products"].items():
            ws = wb.create_sheet(title=sheet_name)

            # Заголовки
            headers = ["Название", "Категория", "Количество", "Единица", "Цена за единицу (₽)", "Итоговая стоимость (₽)"]
            ws.append(headers)

            # Форматирование заголовков
            for cell in ws[1]:
                cell.alignment = alignment

            # Заполнение данных
            for row_idx, product in enumerate(products, start=2):
                # Данные о продукте
                name = product.get("name", "")
                category = product.get("category", "")
                quantity = product.get("quantity", 0)
                unit = product.get("unit", "")
                price_per_unit = product.get("price_per_unit", 0)
                total_cost = product.get("total_cost", quantity * price_per_unit)

                # Заполнение строки
                row = [
                    name,  # Название
                    category,  # Категория
                    quantity,  # Количество
                    unit,  # Единица
                    price_per_unit,  # Цена за единицу
                    total_cost,  # Итоговая стоимость
                ]
                ws.append(row)

                # Форматирование строки
                for cell in ws[row_idx]:
                    cell.alignment = alignment

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

        # Удаляем стандартный лист, если он существует
        if "Sheet" in wb.sheetnames:
            del wb["Sheet"]

        # Сохранение файла
        smeta_dir = os.path.join(os.getcwd(), "smeta_files")
        os.makedirs(smeta_dir, exist_ok=True)
        file_name = os.path.join(smeta_dir, f"smeta_{chat_id}.xlsx")
        wb.save(file_name)
        logger.info(f"Excel-файл успешно создан: {file_name}")

    except Exception as e:
        logger.error(f"Ошибка при создании Excel: {e}")
        raise

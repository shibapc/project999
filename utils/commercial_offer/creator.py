from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from datetime import datetime
import logging
import os
import json

logger = logging.getLogger(__name__)

def load_materials_db() -> dict:
    """Загружает materials.json."""
    try:
        with open("materials.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("Файл materials.json не найден")
        raise
    except json.JSONDecodeError:
        logger.error("Ошибка декодирования materials.json")
        raise

def create_commercial_proposal(chat_id: int, user_data: dict, output_dir: str = "commercial_offer") -> str:
    """Создаёт коммерческое предложение в формате .docx."""
    try:
        # Загружаем materials.json
        materials_db = load_materials_db()
        templates_db = {item["name"]: item for item in materials_db.get("templates", []) if item["category"] == "Изделия"}

        # Создаём директорию для вывода
        os.makedirs(output_dir, exist_ok=True)
        
        # Создаём документ
        doc = Document()

        # Стили документа
        doc.styles['Normal'].font.name = 'Calibri'
        doc.styles['Normal'].font.size = Pt(11)

        # Логотип (раскомментируй, если есть логотип)
        # doc.add_picture("logo.png", width=Inches(1.5))
        # doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Заголовок
        heading = doc.add_heading("Studio of Unique Projects", level=1)
        heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
        heading.runs[0].font.size = Pt(16)
        heading.runs[0].font.color.rgb = RGBColor(0, 51, 102)  # Тёмно-синий

        title = doc.add_heading("Коммерческое предложение", level=1)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title.runs[0].font.size = Pt(14)
        title.runs[0].font.color.rgb = RGBColor(0, 51, 102)

        # Дата
        date_par = doc.add_paragraph(f"Дата: {datetime.now().strftime('%d.%m.%Y')}")
        date_par.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        date_par.runs[0].font.size = Pt(10)

        # Разделитель
        doc.add_paragraph()

        # Одна таблица для всех изделий
        table = doc.add_table(rows=1, cols=5)
        table.style = 'Table Grid'
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = True

        # Заголовки таблицы
        headers = ["№", "Наименование", "Кол-во", "Цена за ед. (₽)", "Общая стоимость (₽)"]
        for i, header in enumerate(headers):
            cell = table.rows[0].cells[i]
            cell.text = header
            cell.paragraphs[0].runs[0].font.size = Pt(10)
            cell.paragraphs[0].runs[0].font.bold = True
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(0, 51, 102)

        # Собираем все изделия из всех листов
        total_cost = 0
        idx = 1
        for sheet in user_data[chat_id]["sheets"]:
            products = user_data[chat_id]["products"].get(sheet, [])
            for product in products:
                product_name = product.get("name")
                # Проверяем, что изделие есть в materials.json
                if product_name not in templates_db:
                    logger.warning(f"Изделие '{product_name}' не найдено в materials.json")
                    continue
                
                # Проверяем наличие обязательных полей
                quantity = product.get("quantity", 1)
                price_per_unit = product.get("price_per_unit")
                total_cost_item = product.get("total_cost", quantity * price_per_unit)
                
                row = table.add_row().cells
                row[0].text = str(idx)
                row[1].text = product_name  # Только название
                row[2].text = str(quantity)
                row[3].text = f"{price_per_unit:.0f}"
                row[4].text = f"{total_cost_item:.0f}"
                total_cost += total_cost_item
                
                # Стили ячеек
                for cell in row:
                    cell.paragraphs[0].runs[0].font.size = Pt(10)
                    cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                
                idx += 1

        # Итоговая строка
        row = table.add_row().cells
        row[0].text = ""
        row[1].text = "Итого"
        row[2].text = ""
        row[3].text = ""
        row[4].text = f"{total_cost:.0f}"
        for cell in row:
            cell.paragraphs[0].runs[0].font.size = Pt(10)
            cell.paragraphs[0].runs[0].font.bold = True
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(0, 51, 102)

        # Разделитель
        doc.add_paragraph()

        # Контактная информация
        contact_heading = doc.add_heading("Контактная информация", level=2)
        contact_heading.runs[0].font.size = Pt(12)
        contact_heading.runs[0].font.color.rgb = RGBColor(0, 51, 102)

        contacts = [
            "Телефон: +7 (123) 456-78-90",
            "Email: contact@studio-unique.ru",
            "Адрес: г. Москва, ул. Примерная, д. 123"
        ]
        for contact in contacts:
            p = doc.add_paragraph(contact)
            p.runs[0].font.size = Pt(10)

        # Подпись
        doc.add_paragraph()
        signature = doc.add_paragraph("Генеральный директор: Иванов И.И.")
        signature.runs[0].font.size = Pt(10)
        signature.runs[0].font.italic = True

        # Сохранение файла
        output_file = os.path.join(output_dir, f"КП_{chat_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx")
        doc.save(output_file)
        logger.info(f"Коммерческое предложение сохранено: {output_file}")
        return output_file

    except Exception as e:
        logger.error(f"Ошибка при создании КП: {str(e)}", exc_info=True)
        raise
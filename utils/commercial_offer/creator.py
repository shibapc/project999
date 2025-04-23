from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime
import os
import json
import logging

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

def create_commercial_proposal_pdf(chat_id: int, user_data: dict, output_dir: str = "commercial_offer") -> str:
    """Создаёт коммерческое предложение в формате PDF."""
    try:
        # Регистрация шрифта Times New Roman
        pdfmetrics.registerFont(TTFont("TimesNewRoman", "utils/commercial_offer/timesnewromanpsmt.ttf"))

        # Загружаем materials.json
        materials_db = load_materials_db()
        templates_db = {item["name"]: item for item in materials_db.get("templates", []) if item["category"] == "Изделия"}

        # Создаём директорию
        os.makedirs(output_dir, exist_ok=True)
        filename = os.path.join(output_dir, f"КП_{chat_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        doc = SimpleDocTemplate(
            filename,
            pagesize=A4,
            rightMargin=15*mm,
            leftMargin=15*mm,
            topMargin=15*mm,
            bottomMargin=15*mm
        )

        # Стили
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name='Header',
            fontName='TimesNewRoman',
            fontSize=12,
            leading=14,
            spaceAfter=5*mm,
            alignment=0  # По левому краю
        ))
        styles.add(ParagraphStyle(
            name='TitleBold',
            fontName='TimesNewRoman',
            fontSize=14,
            leading=16,
            spaceAfter=5*mm,
            alignment=0,
            bold=True
        ))
        styles.add(ParagraphStyle(
            name='Body',
            fontName='TimesNewRoman',
            fontSize=12,
            leading=14,
            spaceAfter=5*mm,
            alignment=0
        ))
        styles.add(ParagraphStyle(
            name='Signature',
            fontName='TimesNewRoman',
            fontSize=12,
            leading=14,
            alignment=2  # По правому краю
        ))

        elements = []

        # Заголовок
        elements.append(Paragraph(
            f"Исх. №{chat_id % 1000:03d} от {datetime.now().strftime('%d.%m.%Y')} г.",
            styles['Header']
        ))

        # Получатель
        elements.append(Paragraph(
            "ООО «_________», в лице __________, действующего на основании __________:",
            styles['Body']
        ))

        # Заголовок КП
        elements.append(Paragraph(
            "<b>Коммерческое предложение</b>",
            styles['TitleBold']
        ))

        # Таблица
        data = [["Наименование конструкций", "Ед. изм.", "Кол-во", "Стоимость за ед., руб.", "Общая стоимость, руб."]]
        total_cost = 0

        for sheet in user_data[chat_id]["sheets"]:
            for item in user_data[chat_id]["products"].get(sheet, []):
                name = item.get("name", "")
                # Проверка изделия
                if name not in templates_db:
                    logger.warning(f"Изделие '{name}' не найдено в materials.json")
                    continue
                unit = templates_db[name].get("unit", "шт")
                qty = item.get("quantity", 1)
                price = item.get("price_per_unit", 0)
                total = item.get("total_cost", qty * price)
                total_cost += total
                data.append([name, unit, str(qty), f"{price:,.0f}", f"{total:,.0f}"])

        # Итоговая строка
        data.append(["", "", "", "Общая стоимость, руб.", f"{total_cost:,.0f}"])

        table = Table(data, colWidths=[80*mm, 25*mm, 20*mm, 35*mm, 35*mm])
        table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#D3D3D3")),  # Серый фон заголовков
            ('ALIGN', (0,0), (0,-1), 'LEFT'),  # Наименование по левому краю
            ('ALIGN', (1,0), (-1,-1), 'CENTER'),  # Остальные столбцы по центру
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('FONTNAME', (0,0), (-1,-1), 'TimesNewRoman'),
            ('FONTSIZE', (0,0), (-1,-1), 12),
            ('FONTWEIGHT', (0,0), (-1,0), 'BOLD'),  # Жирный шрифт для заголовков
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('TOPPADDING', (0,0), (-1,-1), 4),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 8*mm))

        # Итог с НДС
        elements.append(Paragraph(
            f"Общая стоимость в т.ч. НДС 20% — {total_cost:,.0f} руб.",
            styles['Body']
        ))
        elements.append(Spacer(1, 8*mm))

        # Заключительный текст
        elements.append(Paragraph(
            "Надеемся на дальнейшее сотрудничество.",
            styles['Body']
        ))
        elements.append(Spacer(1, 15*mm))

        # Подпись
        elements.append(Paragraph(
            "Генеральный директор ООО «СУП» Зонов Д.А.",
            styles['Signature']
        ))

        doc.build(elements)
        logger.info(f"Коммерческое предложение PDF сохранено: {filename}")
        return filename

    except Exception as e:
        logger.error(f"Ошибка при создании PDF КП: {str(e)}", exc_info=True)
        raise
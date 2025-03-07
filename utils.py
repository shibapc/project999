from openpyxl import Workbook
from openpyxl.styles import Alignment

def create_excel(chat_id: int, user_data: dict):
    wb = Workbook()
    sheets = user_data[chat_id]["sheets"]
    alignment = Alignment(horizontal='center', vertical='center')

    for sheet_name in sheets:
        ws = wb.create_sheet(title=sheet_name)
        header = ["Название", "Количество", "Ед. изм.", "Цена за ед.", "Сумма"]
        ws.append(header)
        
        for cell in ws[1]:
            cell.alignment = alignment
        
        for idx, product in enumerate(user_data[chat_id]["products"][sheet_name], start=2):
            formula = f"=B{idx}*D{idx}"
            row = [
                product["name"],
                product["quantity"],
                product["unit"],
                product["price_per_unit"],
                formula
            ]
            ws.append(row)
            for cell in ws[ws.max_row]:
                cell.alignment = alignment

        total_row_formula = f"=SUM(E2:E{len(user_data[chat_id]['products'][sheet_name]) + 1})"
        total_row = ["ИТОГО", "", "", "", total_row_formula]
        ws.append(total_row)
        for cell in ws[ws.max_row]:
            cell.alignment = alignment

        for row in ws.iter_rows():
            for cell in row:
                cell.alignment = alignment
            ws.row_dimensions[row[0].row].height = 25

        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = (max_length + 2)
            ws.column_dimensions[column].width = adjusted_width

    # Сводный лист
    ws_summary = wb.create_sheet(title="СВОДНЫЙ")
    header = ["№", "МАФ", "Количество", "Итоговая стоимость за 1шт", "Итоговая стоимость за все"]
    ws_summary.append(header)
    
    for cell in ws_summary[1]:
        cell.alignment = alignment

    summary_index = 1
    quantities = user_data[chat_id]["quantities"]
    total_summary_sum_formula_parts = []
    for idx, sheet_name in enumerate(sheets, start=2):
        total_sum_formula = f"=SUM('{sheet_name}'!E2:E{len(user_data[chat_id]['products'][sheet_name]) + 1})"
        total_sum = f"=C{idx}*D{idx}"
        row = [
            summary_index,
            sheet_name,
            quantities[sheet_name],
            total_sum_formula,
            total_sum
        ]
        ws_summary.append(row)
        for cell in ws_summary[ws_summary.max_row]:
            cell.alignment = alignment
        summary_index += 1
        total_summary_sum_formula_parts.append(f"E{idx}")

    total_summary_formula = f"=SUM({','.join(total_summary_sum_formula_parts)})"
    total_summary_row = ["ИТОГО", "", "", "", total_summary_formula]
    ws_summary.append(total_summary_row)
    for cell in ws_summary[ws_summary.max_row]:
        cell.alignment = alignment

    for row in ws_summary.iter_rows():
        for cell in row:
            cell.alignment = alignment
        ws_summary.row_dimensions[row[0].row].height = 25

    for col in ws_summary.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = (max_length + 2)
        ws_summary.column_dimensions[column].width = adjusted_width

    del wb["Sheet"]
    file_name = f"smeta_{chat_id}.xlsx"
    wb.save(file_name)
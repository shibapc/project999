def format_number(value: float) -> str:
    """
    Форматирует число:
    - Убирает .0 в целых числах
    - Разделяет тысячи пробелами
    - Округляет до 2 знаков после запятой
    
    Примеры:
        1000.0 -> "1 000"
        1234.56789 -> "1 234.57"
        50.0 -> "50"
    """
    try:
        # Округляем до 2 знаков
        rounded = round(float(value), 2)
        
        # Если число целое, убираем десятичную часть
        if rounded.is_integer():
            formatted = f"{int(rounded):,}".replace(",", " ")
        else:
            formatted = f"{rounded:,.2f}".replace(",", " ")
        
        return formatted
    except (TypeError, ValueError):
        return str(value)
import os
import logging
import json
from datetime import datetime
from logging.handlers import RotatingFileHandler

def setup_logging():
    # Создаем директорию для логов если её нет
    logs_dir = os.path.join(os.getcwd(), 'logs')
    os.makedirs(logs_dir, exist_ok=True)

    # Формат логов
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    formatter = logging.Formatter(log_format)

    # Основной файл лога
    main_handler = RotatingFileHandler(
        os.path.join(logs_dir, 'bot.log'),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    main_handler.setFormatter(formatter)
    main_handler.setLevel(logging.INFO)

    # Отдельный файл для ошибок
    error_handler = RotatingFileHandler(
        os.path.join(logs_dir, 'errors.log'),
        maxBytes=10*1024*1024,
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)

    # Консольный вывод
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # Настройка корневого логгера
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(main_handler)
    root_logger.addHandler(error_handler)
    root_logger.addHandler(console_handler)

def log_user_state(logger, chat_id, user_data, message=""):
    """Логирование состояния пользователя"""
    try:
        state_log = {
            'timestamp': datetime.now().isoformat(),
            'chat_id': chat_id,
            'message': message,
            'user_data': user_data.get(chat_id, {})
        }
        logger.debug(f"Состояние пользователя: {json.dumps(state_log, indent=2, ensure_ascii=False)}")
    except Exception as e:
        logger.error(f"Ошибка при логировании состояния: {e}")
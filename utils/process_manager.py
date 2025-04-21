import os
import sys
import fcntl
import signal
import logging

logger = logging.getLogger(__name__)

class ProcessManager:
    def __init__(self):
        self.lock_file_path = "/tmp/telegram_bot.lock"
        self.lock_file = None

    def ensure_single_instance(self):
        """Гарантирует запуск только одного экземпляра бота."""
        try:
            self.lock_file = open(self.lock_file_path, "w")
            fcntl.lockf(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            logger.info("Успешно получена блокировка процесса")
            return True
        except IOError:
            logger.error("Бот уже запущен! Завершение работы...")
            return False

    def setup_signal_handlers(self):
        """Настройка обработчиков сигналов."""
        def signal_handler(signum, frame):
            logger.info("Получен сигнал завершения. Останавливаем бота...")
            self.cleanup()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # kill
        logger.info("Обработчики сигналов настроены")

    def cleanup(self):
        """Очистка ресурсов при завершении."""
        if self.lock_file:
            self.lock_file.close()
            try:
                os.remove(self.lock_file_path)
                logger.info("Файл блокировки удален")
            except OSError as e:
                logger.error(f"Ошибка при удалении файла блокировки: {e}")

process_manager = ProcessManager()
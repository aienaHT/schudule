import os
import sys
from app import app

if __name__ == '__main__':
    # Получаем настройки из переменных окружения или используем значения по умолчанию
    host = os.environ.get('FLASK_HOST', '192.168.0.185')
    port = int(os.environ.get('FLASK_PORT', 5000))
    
    print(f"🚀 Запуск сервера расписания...")
    print(f"📡 Внешний адрес: http://{host}:{port}")
    print(f"🏠 Локальный адрес: http://localhost:{port}")
    print("=" * 50)
    print("⚡ Для остановки нажмите Ctrl+C")
    print("=" * 50)
    
    app.run(host=host, port=port, debug=True)
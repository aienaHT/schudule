import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import *
from sqlalchemy import inspect, text


def migrate_database():
    with app.app_context():
        inspector = inspect(db.engine)

        # Проверяем существование таблицы schedule_entry
        if 'schedule_entry' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('schedule_entry')]

            # Добавляем колонку is_combined если её нет
            if 'is_combined' not in columns:
                print("Добавляем колонку is_combined в таблицу schedule_entry...")
                try:
                    with db.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE schedule_entry ADD COLUMN is_combined BOOLEAN DEFAULT FALSE"))
                        conn.commit()
                    print("Колонка is_combined добавлена успешно!")
                except Exception as e:
                    print(f"Ошибка при добавлении колонки is_combined: {e}")

            # Добавляем колонку is_combined в таблицу main_schedule_entry если её нет
            if 'main_schedule_entry' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('main_schedule_entry')]
                if 'is_combined' not in columns:
                    print("Добавляем колонку is_combined в таблицу main_schedule_entry...")
                    try:
                        with db.engine.connect() as conn:
                            conn.execute(
                                text("ALTER TABLE main_schedule_entry ADD COLUMN is_combined BOOLEAN DEFAULT FALSE"))
                            conn.commit()
                        print("Колонка is_combined добавлена в main_schedule_entry успешно!")
                    except Exception as e:
                        print(f"Ошибка при добавлении колонки is_combined в main_schedule_entry: {e}")

        print("Миграция базы данных завершена!")


if __name__ == '__main__':
    migrate_database()
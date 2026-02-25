import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import *
from sqlalchemy import inspect, text


def fix_database_complete():
    with app.app_context():
        inspector = inspect(db.engine)

        print("Начинаем полное исправление базы данных...")

        # ========== ИСПРАВЛЯЕМ ТАБЛИЦУ app_settings ==========
        if 'app_settings' in inspector.get_table_names():
            print("Проверяем таблицу app_settings...")

            # Получаем информацию о колонках
            with db.engine.connect() as conn:
                columns = conn.execute(text("PRAGMA table_info(app_settings)")).fetchall()
                column_names = [col[1] for col in columns]

                # Проверяем наличие колонки id
                if 'id' not in column_names:
                    print("Таблица app_settings имеет неправильную структуру. Пересоздаем...")

                    # Сохраняем существующие данные если есть
                    try:
                        existing_data = conn.execute(text("SELECT key, value FROM app_settings")).fetchall()
                    except:
                        existing_data = []

                    # Удаляем старую таблицу
                    conn.execute(text("DROP TABLE app_settings"))
                    conn.commit()

                    # Создаем новую таблицу с правильной структурой
                    conn.execute(text("""
                        CREATE TABLE app_settings (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            key VARCHAR(50) NOT NULL UNIQUE,
                            value VARCHAR(200) NOT NULL
                        )
                    """))
                    conn.commit()

                    # Восстанавливаем данные
                    for key, value in existing_data:
                        try:
                            conn.execute(
                                text("INSERT INTO app_settings (key, value) VALUES (:key, :value)"),
                                {"key": key, "value": value}
                            )
                        except:
                            pass
                    conn.commit()
                    print("Таблица app_settings успешно пересоздана!")
                else:
                    print("Таблица app_settings в порядке.")
        else:
            print("Создаем таблицу app_settings...")
            with db.engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE app_settings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        key VARCHAR(50) NOT NULL UNIQUE,
                        value VARCHAR(200) NOT NULL
                    )
                """))
                conn.commit()
                print("Таблица app_settings создана!")

        # ========== ПРОВЕРЯЕМ И СОЗДАЕМ НАЧАЛЬНЫЕ НАСТРОЙКИ ==========
        try:
            # Проверяем настройку current_week
            week_setting = conn.execute(
                text("SELECT * FROM app_settings WHERE key = 'current_week'")
            ).fetchone()

            if not week_setting:
                conn.execute(
                    text("INSERT INTO app_settings (key, value) VALUES ('current_week', '1')")
                )
                print("Добавлена настройка current_week = 1")

            # Проверяем настройку current_semester
            semester_setting = conn.execute(
                text("SELECT * FROM app_settings WHERE key = 'current_semester'")
            ).fetchone()

            if not semester_setting:
                conn.execute(
                    text("INSERT INTO app_settings (key, value) VALUES ('current_semester', '1')")
                )
                print("Добавлена настройка current_semester = 1")

            conn.commit()

        except Exception as e:
            print(f"Ошибка при создании настроек: {e}")

        # ========== ПРОВЕРЯЕМ ДРУГИЕ ТАБЛИЦЫ ==========

        # Проверяем таблицу group_subject
        if 'group_subject' in inspector.get_table_names():
            with db.engine.connect() as conn:
                columns = conn.execute(text("PRAGMA table_info(group_subject)")).fetchall()
                column_names = [col[1] for col in columns]

                # Добавляем недостающие колонки
                if 'total_hours_semester1' not in column_names:
                    print("Добавляем total_hours_semester1 в group_subject...")
                    conn.execute(text("ALTER TABLE group_subject ADD COLUMN total_hours_semester1 INTEGER DEFAULT 0"))

                if 'total_hours_semester2' not in column_names:
                    print("Добавляем total_hours_semester2 в group_subject...")
                    conn.execute(text("ALTER TABLE group_subject ADD COLUMN total_hours_semester2 INTEGER DEFAULT 0"))

                if 'teacher_id' not in column_names:
                    print("Добавляем teacher_id в group_subject...")
                    conn.execute(text("ALTER TABLE group_subject ADD COLUMN teacher_id INTEGER"))

                conn.commit()

        # Проверяем таблицу schedule_entry
        if 'schedule_entry' in inspector.get_table_names():
            with db.engine.connect() as conn:
                columns = conn.execute(text("PRAGMA table_info(schedule_entry)")).fetchall()
                column_names = [col[1] for col in columns]

                if 'is_combined' not in column_names:
                    print("Добавляем is_combined в schedule_entry...")
                    conn.execute(text("ALTER TABLE schedule_entry ADD COLUMN is_combined BOOLEAN DEFAULT FALSE"))

                if 'week_parity' not in column_names:
                    print("Добавляем week_parity в schedule_entry...")
                    conn.execute(text("ALTER TABLE schedule_entry ADD COLUMN week_parity VARCHAR(10) DEFAULT 'both'"))

                conn.commit()

        # Проверяем таблицу main_schedule_entry
        if 'main_schedule_entry' in inspector.get_table_names():
            with db.engine.connect() as conn:
                columns = conn.execute(text("PRAGMA table_info(main_schedule_entry)")).fetchall()
                column_names = [col[1] for col in columns]

                if 'is_combined' not in column_names:
                    print("Добавляем is_combined в main_schedule_entry...")
                    conn.execute(text("ALTER TABLE main_schedule_entry ADD COLUMN is_combined BOOLEAN DEFAULT FALSE"))

                if 'week_parity' not in column_names:
                    print("Добавляем week_parity в main_schedule_entry...")
                    conn.execute(
                        text("ALTER TABLE main_schedule_entry ADD COLUMN week_parity VARCHAR(10) DEFAULT 'both'"))

                conn.commit()

        # Проверяем таблицу group_practice
        if 'group_practice' not in inspector.get_table_names():
            print("Создаем таблицу group_practice...")
            with db.engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE group_practice (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        group_id INTEGER NOT NULL UNIQUE,
                        day VARCHAR(20) NOT NULL,
                        subject_id INTEGER,
                        teacher_id INTEGER,
                        room_id INTEGER,
                        FOREIGN KEY (group_id) REFERENCES "group" (id),
                        FOREIGN KEY (subject_id) REFERENCES subject (id),
                        FOREIGN KEY (teacher_id) REFERENCES teacher (id),
                        FOREIGN KEY (room_id) REFERENCES room (id)
                    )
                """))
                conn.commit()
                print("Таблица group_practice создана!")

        print("\n=== ПРОВЕРКА ТЕКУЩИХ НАСТРОЕК ===")
        with db.engine.connect() as conn:
            settings = conn.execute(text("SELECT * FROM app_settings")).fetchall()
            for setting in settings:
                print(f"  {setting[1]} = {setting[2]}")

        print("\n✅ База данных полностью исправлена!")


if __name__ == '__main__':
    fix_database_complete()
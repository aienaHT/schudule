import sqlite3
import pandas as pd
import os
from pathlib import Path
from collections import namedtuple
from datetime import datetime

# Модели данных
Teacher = namedtuple("Teacher", ["id", "name"])
Subject = namedtuple("Subject", ["id", "name"])
Group = namedtuple("Group", ["id", "name"])
Room = namedtuple("Room", ["id", "name"])
ScheduleEntry = namedtuple("ScheduleEntry", 
                           ["id", "group_name", "subject_name", "teacher_name", 
                            "room_name", "day", "lesson_number", "week_number"])

class DatabaseManager:
    def __init__(self, db_name="schedule.db"):
        self.db_name = db_name
        self.conn = None
        self._connect()
        print(f"Подключено к базе данных: {self.db_name}")

    def _connect(self):
        try:
            self.conn = sqlite3.connect(self.db_name)
            self.conn.row_factory = sqlite3.Row
        except sqlite3.Error as e:
            print(f"Ошибка подключения к базе данных: {e}")
            self.conn = None

    def _close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def _execute(self, query, params=(), fetch_one=False, fetch_all=False, commit=False):
        if not self.conn:
            self._connect()
            if not self.conn:
                return None

        try:
            cursor = self.conn.cursor()
            cursor.execute(query, params)
            if commit:
                self.conn.commit()
            if fetch_one:
                return cursor.fetchone()
            if fetch_all:
                return cursor.fetchall()
            return cursor.lastrowid # Для INSERT операций
        except sqlite3.Error as e:
            print(f"Ошибка выполнения запроса: {e}")
            print(f"Запрос: {query}, Параметры: {params}")
            return None

    def create_tables(self):
        queries = [
            """
            CREATE TABLE IF NOT EXISTS teachers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS schedule_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                teacher_id INTEGER NOT NULL,
                room_id INTEGER NOT NULL,
                day TEXT NOT NULL,
                lesson_number INTEGER NOT NULL,
                week_number INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES groups(id),
                FOREIGN KEY (subject_id) REFERENCES subjects(id),
                FOREIGN KEY (teacher_id) REFERENCES teachers(id),
                FOREIGN KEY (room_id) REFERENCES rooms(id),
                UNIQUE (group_id, day, lesson_number, week_number),
                UNIQUE (teacher_id, day, lesson_number, week_number),
                UNIQUE (room_id, day, lesson_number, week_number)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS teacher_subject_hours (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                total_hours INTEGER NOT NULL,
                used_hours INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (teacher_id) REFERENCES teachers(id),
                FOREIGN KEY (subject_id) REFERENCES subjects(id),
                UNIQUE (teacher_id, subject_id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        ]
        for query in queries:
            self._execute(query, commit=True)
        print("Таблицы проверены/созданы.")
        
        # Проверяем существование столбца week_number и добавляем его если нужно
        try:
            self._execute("SELECT week_number FROM schedule_entries LIMIT 1", fetch_one=True)
        except sqlite3.OperationalError:
            print("Добавляем отсутствующий столбец week_number...")
            self._execute("ALTER TABLE schedule_entries ADD COLUMN week_number INTEGER NOT NULL DEFAULT 1", commit=True)

        # Проверяем существование столбца created_at и добавляем его если нужно
        try:
            self._execute("SELECT created_at FROM schedule_entries LIMIT 1", fetch_one=True)
        except sqlite3.OperationalError:
            print("Добавляем отсутствующий столбец created_at...")
            self._execute("ALTER TABLE schedule_entries ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP", commit=True)

    def populate_initial_data(self, teachers_data, subjects_data, groups_data, rooms_data):
        # Проверяем, есть ли уже начальные данные
        if self._execute("SELECT COUNT(*) FROM teachers", fetch_one=True)[0] > 0:
            # Проверяем также, установлена ли уже текущая неделя
            if self._execute("SELECT value FROM app_settings WHERE key = 'current_week'", fetch_one=True):
                print("Начальные данные уже существуют. Пропускаем заполнение.")
                return

        print("Заполнение начальных данных...")
        
        # Заполнение преподавателей и их предметов/часов
        for teacher_name, subjects_info in teachers_data.items():
            teacher_id = self.add_teacher(teacher_name)
            if teacher_id:
                for subject_name, total_hours in subjects_info.items():
                    subject_id = self.add_subject(subject_name)
                    if subject_id:
                        self.add_teacher_subject_hours(teacher_id, subject_id, total_hours)

        # Заполнение остальных данных
        for subject_name in subjects_data:
            self.add_subject(subject_name) # На случай, если предмет не был привязан к преподавателю
        for group_name in groups_data:
            self.add_group(group_name)
        for room_name in rooms_data:
            self.add_room(room_name)

        # Установка начальной недели
        self.set_setting('current_week', '1')

        print("Начальные данные заполнены.")

    # --- Методы для работы с таблицами ---
    def add_teacher(self, name):
        return self._execute("INSERT OR IGNORE INTO teachers (name) VALUES (?)", (name,), commit=True)

    def get_teacher_id_by_name(self, name):
        result = self._execute("SELECT id FROM teachers WHERE name = ?", (name,), fetch_one=True)
        return result[0] if result else None

    def get_teacher_by_id(self, teacher_id):
        result = self._execute("SELECT id, name FROM teachers WHERE id = ?", (teacher_id,), fetch_one=True)
        return Teacher(result[0], result[1]) if result else None
    
    def get_all_teachers(self):
        results = self._execute("SELECT id, name FROM teachers", fetch_all=True)
        return [Teacher(row['id'], row['name']) for row in results] if results else []

    def add_subject(self, name):
        return self._execute("INSERT OR IGNORE INTO subjects (name) VALUES (?)", (name,), commit=True)

    def get_subject_id_by_name(self, name):
        result = self._execute("SELECT id FROM subjects WHERE name = ?", (name,), fetch_one=True)
        return result[0] if result else None

    def get_subject_by_id(self, subject_id):
        result = self._execute("SELECT id, name FROM subjects WHERE id = ?", (subject_id,), fetch_one=True)
        return Subject(result[0], result[1]) if result else None

    def add_group(self, name):
        return self._execute("INSERT OR IGNORE INTO groups (name) VALUES (?)", (name,), commit=True)

    def get_group_id_by_name(self, name):
        result = self._execute("SELECT id FROM groups WHERE name = ?", (name,), fetch_one=True)
        return result[0] if result else None

    def get_group_by_id(self, group_id):
        result = self._execute("SELECT id, name FROM groups WHERE id = ?", (group_id,), fetch_one=True)
        return Group(result[0], result[1]) if result else None

    def add_room(self, name):
        return self._execute("INSERT OR IGNORE INTO rooms (name) VALUES (?)", (name,), commit=True)

    def get_room_id_by_name(self, name):
        result = self._execute("SELECT id FROM rooms WHERE name = ?", (name,), fetch_one=True)
        return result[0] if result else None

    def get_room_by_id(self, room_id):
        result = self._execute("SELECT id, name FROM rooms WHERE id = ?", (room_id,), fetch_one=True)
        return Room(result[0], result[1]) if result else None

    def get_all_rooms(self):
        results = self._execute("SELECT id, name FROM rooms", fetch_all=True)
        return [Room(row['id'], row['name']) for row in results] if results else []

    def add_teacher_subject_hours(self, teacher_id, subject_id, total_hours):
        # Если запись уже существует, обновляем total_hours
        existing_entry = self._execute(
            "SELECT id FROM teacher_subject_hours WHERE teacher_id = ? AND subject_id = ?",
            (teacher_id, subject_id), fetch_one=True
        )
        if existing_entry:
            self._execute(
                "UPDATE teacher_subject_hours SET total_hours = ? WHERE id = ?",
                (total_hours, existing_entry[0]), commit=True
            )
            return existing_entry[0]
        else:
            return self._execute(
                "INSERT INTO teacher_subject_hours (teacher_id, subject_id, total_hours, used_hours) VALUES (?, ?, ?, 0)",
                (teacher_id, subject_id, total_hours), commit=True
            )

    def update_teacher_used_hours(self, teacher_id, subject_id, amount=2):
        self._execute(
            """
            UPDATE teacher_subject_hours 
            SET used_hours = used_hours + ? 
            WHERE teacher_id = ? AND subject_id = ?
            """,
            (amount, teacher_id, subject_id), commit=True
        )

    def get_teacher_subject_remaining_hours(self, teacher_id, subject_id):
        result = self._execute(
            "SELECT total_hours, used_hours FROM teacher_subject_hours WHERE teacher_id = ? AND subject_id = ?",
            (teacher_id, subject_id), fetch_one=True
        )
        if result:
            return result['total_hours'] - result['used_hours']
        return 0 # Если нет записи, считаем 0 оставшихся часов

    def get_all_teacher_load_info(self):
        query = """
            SELECT
                T.name AS teacher_name,
                S.name AS subject_name,
                TSH.total_hours,
                TSH.used_hours
            FROM teachers AS T
            JOIN teacher_subject_hours AS TSH ON T.id = TSH.teacher_id
            JOIN subjects AS S ON S.id = TSH.subject_id
            ORDER BY T.name, S.name;
        """
        return self._execute(query, fetch_all=True)

    def add_schedule_entry(self, group_id, subject_id, teacher_id, room_id, day, lesson_number, week_number=None):
        if week_number is None:
            week_number = self.get_current_week()

        # Проверка конфликтов перед добавлением
        conflicts = [
            ("SELECT id FROM schedule_entries WHERE group_id = ? AND day = ? AND lesson_number = ? AND week_number = ?", 
             (group_id, day, lesson_number, week_number)),
            ("SELECT id FROM schedule_entries WHERE teacher_id = ? AND day = ? AND lesson_number = ? AND week_number = ?", 
             (teacher_id, day, lesson_number, week_number)),
            ("SELECT id FROM schedule_entries WHERE room_id = ? AND day = ? AND lesson_number = ? AND week_number = ?", 
             (room_id, day, lesson_number, week_number))
        ]
        
        for query, params in conflicts:
            if self._execute(query, params, fetch_one=True):
                return None # Возвращаем None, если есть конфликт
        
        # Если конфликтов нет, добавляем запись
        return self._execute(
            """
            INSERT INTO schedule_entries 
            (group_id, subject_id, teacher_id, room_id, day, lesson_number, week_number) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (group_id, subject_id, teacher_id, room_id, day, lesson_number, week_number), commit=True
        )

    def get_all_schedule_entries(self, week_number=None):
        if week_number is None:
            week_number = self.get_current_week()
        
        query = """
            SELECT 
                SE.id, G.name AS group_name, S.name AS subject_name, 
                T.name AS teacher_name, R.name AS room_name, 
                SE.day, SE.lesson_number, SE.week_number
            FROM schedule_entries AS SE
            JOIN groups AS G ON SE.group_id = G.id
            JOIN subjects AS S ON SE.subject_id = S.id
            JOIN teachers AS T ON SE.teacher_id = T.id
            JOIN rooms AS R ON SE.room_id = R.id
            WHERE SE.week_number = ?
            ORDER BY SE.day, SE.lesson_number, G.name
        """
        results = self._execute(query, (week_number,), fetch_all=True)
        return [ScheduleEntry(*row) for row in results] if results else []

    def get_schedule_entries_for_day(self, day, week_number=None):
        if week_number is None:
            week_number = self.get_current_week()

        query = """
            SELECT 
                SE.id, G.name AS group_name, S.name AS subject_name, 
                T.name AS teacher_name, R.name AS room_name, 
                SE.day, SE.lesson_number, SE.week_number
            FROM schedule_entries AS SE
            JOIN groups AS G ON SE.group_id = G.id
            JOIN subjects AS S ON SE.subject_id = S.id
            JOIN teachers AS T ON SE.teacher_id = T.id
            JOIN rooms AS R ON SE.room_id = R.id
            WHERE SE.day = ? AND SE.week_number = ?
            ORDER BY SE.lesson_number, G.name
        """
        results = self._execute(query, (day, week_number), fetch_all=True)
        return [ScheduleEntry(*row) for row in results] if results else []

    def update_schedule_entry(self, entry_id, group_id=None, subject_id=None, teacher_id=None, room_id=None, day=None, lesson_number=None):
        set_parts = []
        params = []
        
        # Получаем текущие значения записи для валидации конфликтов
        current_entry = self._execute("SELECT * FROM schedule_entries WHERE id = ?", (entry_id,), fetch_one=True)
        if not current_entry:
            print(f"Ошибка: Запись с ID {entry_id} не найдена.")
            return False

        # Подготовка параметров для обновления
        if group_id is not None and group_id != current_entry['group_id']:
            set_parts.append("group_id = ?")
            params.append(group_id)
        if subject_id is not None and subject_id != current_entry['subject_id']:
            set_parts.append("subject_id = ?")
            params.append(subject_id)
        if teacher_id is not None and teacher_id != current_entry['teacher_id']:
            set_parts.append("teacher_id = ?")
            params.append(teacher_id)
        if room_id is not None and room_id != current_entry['room_id']:
            set_parts.append("room_id = ?")
            params.append(room_id)
        if day is not None and day != current_entry['day']:
            set_parts.append("day = ?")
            params.append(day)
        if lesson_number is not None and lesson_number != current_entry['lesson_number']:
            set_parts.append("lesson_number = ?")
            params.append(lesson_number)
        
        if not set_parts:
            # print("Нет данных для обновления, или значения совпадают с текущими.")
            return True # Ничего не изменилось, но операция успешна

        # Для проверки конфликтов используем новые (или старые, если не менялись) значения
        final_group_id = group_id if group_id is not None else current_entry['group_id']
        final_teacher_id = teacher_id if teacher_id is not None else current_entry['teacher_id']
        final_room_id = room_id if room_id is not None else current_entry['room_id']
        final_day = day if day is not None else current_entry['day']
        final_lesson_number = lesson_number if lesson_number is not None else current_entry['lesson_number']
        final_week_number = current_entry['week_number'] # Неделя не меняется при редактировании записи

        # Проверка конфликтов с ДРУГИМИ записями (исключая текущую)
        conflicts = [
            ("SELECT id FROM schedule_entries WHERE group_id = ? AND day = ? AND lesson_number = ? AND week_number = ? AND id != ?", 
             (final_group_id, final_day, final_lesson_number, final_week_number, entry_id)),
            ("SELECT id FROM schedule_entries WHERE teacher_id = ? AND day = ? AND lesson_number = ? AND week_number = ? AND id != ?", 
             (final_teacher_id, final_day, final_lesson_number, final_week_number, entry_id)),
            ("SELECT id FROM schedule_entries WHERE room_id = ? AND day = ? AND lesson_number = ? AND week_number = ? AND id != ?", 
             (final_room_id, final_day, final_lesson_number, final_week_number, entry_id))
        ]
        
        for query_check, params_check in conflicts:
            if self._execute(query_check, params_check, fetch_one=True):
                print(f"Ошибка: Изменение приведет к конфликту расписания. Запись не обновлена.")
                return False # Возвращаем False, если есть конфликт
        
        query = f"UPDATE schedule_entries SET {', '.join(set_parts)} WHERE id = ?"
        params.append(entry_id)
        
        return self._execute(query, tuple(params), commit=True) is not None

    def delete_schedule_entry(self, entry_id):
        # При удалении записи, часы преподавателя по этому предмету должны быть "возвращены"
        # Получаем данные удаляемой записи
        entry_data = self._execute(
            "SELECT teacher_id, subject_id FROM schedule_entries WHERE id = ?",
            (entry_id,), fetch_one=True
        )

        if entry_data:
            teacher_id = entry_data['teacher_id']
            subject_id = entry_data['subject_id']
            # Уменьшаем использованные часы преподавателя
            self._execute(
                """
                UPDATE teacher_subject_hours 
                SET used_hours = used_hours - 2 
                WHERE teacher_id = ? AND subject_id = ? AND used_hours >= 2
                """,
                (teacher_id, subject_id), commit=True
            )

        return self._execute("DELETE FROM schedule_entries WHERE id = ?", (entry_id,), commit=True) is not None

    def delete_week(self, week_number):
        # При удалении недели, также сбрасываем used_hours для преподавателей
        # так как это расписание больше не существует.
        self._execute("UPDATE teacher_subject_hours SET used_hours = 0", commit=True)
        return self._execute("DELETE FROM schedule_entries WHERE week_number = ?", (week_number,), commit=True) is not None

    # --- Методы для работы с app_settings (новое) ---
    def set_setting(self, key, value):
        self._execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)", (key, str(value)), commit=True)

    def get_setting(self, key, default=None):
        result = self._execute("SELECT value FROM app_settings WHERE key = ?", (key,), fetch_one=True)
        return result[0] if result else default

    # --- Методы для работы с текущей неделей (новое) ---
    def get_current_week(self):
        week = self.get_setting('current_week', '1') # По умолчанию неделя 1
        return int(week)

    def get_next_week_schedule(self):
        current_week = self.get_current_week()
        next_week = current_week + 1
        self.set_setting('current_week', next_week)
        
        # Сброс часов использования преподавателей при переходе на новую неделю
        # Это предотвращает накопление `used_hours` через недели, что важно для еженедельного планирования.
        self._execute("UPDATE teacher_subject_hours SET used_hours = 0", commit=True)

        return next_week
    
    # --- Экспорт в Excel ---
    def export_schedule_to_excel(self, day=None, week_number=None, filename="schedule_export.xlsx"):
        if week_number is None:
            week_number = self.get_current_week()

        if day:
            entries = self.get_schedule_entries_for_day(day, week_number)
            if entries:
                filename = filename.replace(".xlsx", f"_{day}.xlsx") # Добавляем день к имени файла
        else:
            entries = self.get_all_schedule_entries(week_number)
            if entries:
                filename = filename.replace(".xlsx", f"_week_{week_number}.xlsx") # Добавляем номер недели к имени файла
            
        if not entries:
            print(f"Нет данных для экспорта за неделю {week_number}" + (f" на день {day}" if day else ""))
            return False

        # Преобразование namedtuple в список словарей для DataFrame
        data = [entry._asdict() for entry in entries]
        df = pd.DataFrame(data)

        # Переименование колонок для читаемости
        df = df.rename(columns={
            'group_name': 'Группа',
            'subject_name': 'Предмет',
            'teacher_name': 'Преподаватель',
            'room_name': 'Аудитория',
            'day': 'День Недели',
            'lesson_number': 'Номер Пары',
            'week_number': 'Неделя'
        })
        
        # Удаляем ненужный 'id'
        df = df.drop(columns=['id'])

        try:
            # Получаем путь к папке Загрузки (Downloads)
            downloads_path = Path.home() / "Downloads"
            filepath = downloads_path / filename
            
            df.to_excel(filepath, index=False)
            print(f"Расписание успешно экспортировано в '{filepath}'")
            return True
        except Exception as e:
            print(f"Ошибка при экспорте в Excel: {e}")
            return False
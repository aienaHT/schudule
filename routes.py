# routes.py
from flask import render_template, request, jsonify, flash, redirect, url_for, send_file
from flask_login import login_required, current_user, login_user, logout_user
from models import db, User, Teacher, Subject, Group, Room, ScheduleEntry, MainScheduleEntry, AppSettings
from initial_data import AVAILABLE_DAYS, GROUPS, SUBJECTS, ROOMS, TEACHER_INITIAL_LOAD, AVAILABLE_PAIRS, get_lesson_time, WEEK_PARITIES, SEMESTERS, MAX_WEEKS, get_pair_number
import pandas as pd
import os
from datetime import datetime
import io
from openpyxl import Workbook

def init_routes(app):
    
    # Добавляем фильтр для форматирования пары
    @app.template_filter('pair_format')
    def pair_format(lesson_number, day):
        pair_num = get_pair_number(day, lesson_number)
        time = get_lesson_time(day, lesson_number)
        if time:
            return f"Пара {pair_num} (урок {lesson_number} - {time})"
        return f"Пара {pair_num} (урок {lesson_number})"
    
    # Добавляем фильтр для определения четности недели
    @app.template_filter('week_parity_text')
    def week_parity_text(parity):
        if parity == 'even':
            return 'чётная'
        elif parity == 'odd':
            return 'нечётная'
        else:
            return 'всегда'
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            
            user = User.query.filter_by(username=username).first()
            if user and user.check_password(password):
                login_user(user)
                flash('Вы успешно вошли!', 'success')
                return redirect(url_for('admin'))
            else:
                flash('Неверное имя пользователя или пароль', 'error')
        
        return render_template('login.html')
    
    @app.route('/logout')
    def logout():
        logout_user()
        flash('Вы вышли из системы', 'info')
        return redirect(url_for('index'))
    
    @app.route('/')
    def index():
        return render_template('index.html')
    
    @app.route('/schedule')
    def schedule():
        day = request.args.get('day', 'Понедельник')
        week = request.args.get('week', '')
        semester = request.args.get('semester', '')
        schedule_type = request.args.get('type', 'current')
        
        current_semester = get_current_semester()
        if semester:
            current_semester = int(semester)
        
        if week:
            current_week = int(week)
        else:
            current_week = get_current_week()
        
        current_parity = 'even' if current_week % 2 == 0 else 'odd'
        
        if schedule_type == 'main':
            entries = MainScheduleEntry.query.filter(
                MainScheduleEntry.day == day,
                MainScheduleEntry.semester == current_semester
            ).filter(
                (MainScheduleEntry.week_parity == 'both') |
                (MainScheduleEntry.week_parity == current_parity)
            ).order_by(MainScheduleEntry.lesson_number).all()
        else:
            entries = ScheduleEntry.query.filter(
                ScheduleEntry.day == day,
                ScheduleEntry.semester == current_semester,
                ScheduleEntry.week_number == current_week
            ).order_by(ScheduleEntry.lesson_number).all()
        
        schedule_data = {}
        all_groups = set()
        
        for entry in entries:
            group_name = entry.group.name
            all_groups.add(group_name)
            if group_name not in schedule_data:
                schedule_data[group_name] = {}
            
            pair_num = get_pair_number(entry.day, entry.lesson_number)
            if pair_num not in schedule_data[group_name]:
                schedule_data[group_name][pair_num] = []
            
            schedule_data[group_name][pair_num].append({
                'subject': entry.subject.name,
                'teacher': entry.teacher.name,
                'room': entry.room.name,
                'lesson_number': entry.lesson_number,
                'time': get_lesson_time(entry.day, entry.lesson_number),
                'is_changed': getattr(entry, 'is_changed', False)
            })
        
        return render_template('schedule.html',
                             days=AVAILABLE_DAYS,
                             selected_day=day,
                             schedule_data=schedule_data,
                             groups=sorted(all_groups),
                             current_week=current_week,
                             current_semester=current_semester,
                             schedule_type=schedule_type,
                             week_parity=current_parity)
    
    @app.route('/admin')
    @login_required
    def admin():
        if current_user.role != 'admin':
            flash('Доступ запрещен', 'error')
            return redirect(url_for('index'))
        
        current_week = get_current_week()
        current_semester = get_current_semester()
        week_parity = 'even' if current_week % 2 == 0 else 'odd'
        
        entries = ScheduleEntry.query.filter_by(
            week_number=current_week, 
            semester=current_semester
        ).order_by(
            ScheduleEntry.day, ScheduleEntry.lesson_number, ScheduleEntry.group_id
        ).all()
        
        main_entries = MainScheduleEntry.query.filter_by(
            semester=current_semester
        ).filter(
            (MainScheduleEntry.week_parity == 'both') |
            (MainScheduleEntry.week_parity == week_parity)
        ).order_by(
            MainScheduleEntry.day, MainScheduleEntry.lesson_number, MainScheduleEntry.group_id
        ).all()
        
        all_teachers = Teacher.query.order_by(Teacher.name).all()
        teachers_list = [teacher.name for teacher in all_teachers]
        
        return render_template('admin.html', 
                             entries=entries,
                             main_entries=main_entries,
                             days=AVAILABLE_DAYS,
                             groups=GROUPS,
                             subjects=SUBJECTS,
                             teachers=teachers_list,
                             rooms=ROOMS,
                             week_parities=WEEK_PARITIES,
                             current_week=current_week,
                             current_semester=current_semester,
                             week_parity=week_parity)
    
    @app.route('/api/add_schedule', methods=['POST'])
    @login_required
    def add_schedule():
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        try:
            data = request.get_json()
            current_week = get_current_week()
            current_semester = get_current_semester()
            is_main = data.get('is_main', 'false') == 'true'
            week_parity = data.get('week_parity', 'both')
            
            group = Group.query.filter_by(name=data['group']).first()
            if not group:
                return jsonify({'success': False, 'message': 'Группа не найдена'})
            
            if is_main:
                conflict = MainScheduleEntry.query.filter_by(
                    group_id=group.id,
                    day=data['day'],
                    lesson_number=data['lesson_number'],
                    semester=current_semester
                ).filter(
                    (MainScheduleEntry.week_parity == week_parity) |
                    (MainScheduleEntry.week_parity == 'both') |
                    (week_parity == 'both')
                ).first()
            else:
                conflict = ScheduleEntry.query.filter_by(
                    group_id=group.id,
                    day=data['day'],
                    lesson_number=data['lesson_number'],
                    week_number=current_week,
                    semester=current_semester
                ).first()
            
            if conflict:
                return jsonify({'success': False, 'message': 'Конфликт: группа уже занята в это время'})
            
            subject = Subject.query.filter_by(name=data['subject']).first()
            teacher = Teacher.query.filter_by(name=data['teacher']).first()
            room = Room.query.filter_by(name=data['room']).first()
            
            if not all([group, subject, teacher, room]):
                return jsonify({'success': False, 'message': 'Неверные данные'})
            
            if is_main:
                entry = MainScheduleEntry(
                    group_id=group.id,
                    subject_id=subject.id,
                    teacher_id=teacher.id,
                    room_id=room.id,
                    day=data['day'],
                    lesson_number=data['lesson_number'],
                    week_parity=week_parity,
                    semester=current_semester
                )
            else:
                entry = ScheduleEntry(
                    group_id=group.id,
                    subject_id=subject.id,
                    teacher_id=teacher.id,
                    room_id=room.id,
                    day=data['day'],
                    lesson_number=data['lesson_number'],
                    week_number=current_week,
                    week_parity=week_parity,
                    semester=current_semester,
                    is_changed=True
                )
            
            db.session.add(entry)
            db.session.commit()
            
            if is_main:
                update_current_schedule_from_main(current_week, current_semester)
            
            return jsonify({'success': True, 'message': 'Успешно добавлено!'})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'})
    
    @app.route('/api/delete_schedule/<int:entry_id>', methods=['DELETE'])
    @login_required
    def delete_schedule(entry_id):
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        try:
            entry = ScheduleEntry.query.get(entry_id)
            if entry:
                db.session.delete(entry)
                db.session.commit()
                return jsonify({'success': True, 'message': 'Запись удалена'})
            else:
                return jsonify({'success': False, 'message': 'Запись не найдена'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'})
    
    @app.route('/api/delete_main_schedule/<int:entry_id>', methods=['DELETE'])
    @login_required
    def delete_main_schedule(entry_id):
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        try:
            entry = MainScheduleEntry.query.get(entry_id)
            if entry:
                db.session.delete(entry)
                db.session.commit()
                
                current_week = get_current_week()
                current_semester = get_current_semester()
                update_current_schedule_from_main(current_week, current_semester)
                
                return jsonify({'success': True, 'message': 'Запись основного расписания удалена'})
            else:
                return jsonify({'success': False, 'message': 'Запись не найдена'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'})
    
    @app.route('/api/next_week', methods=['POST'])
    @login_required
    def next_week():
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        try:
            current_week = get_current_week()
            next_week = current_week + 1
            
            setting = AppSettings.query.filter_by(key='current_week').first()
            if setting:
                setting.value = str(next_week)
            else:
                setting = AppSettings(key='current_week', value=str(next_week))
                db.session.add(setting)
            
            current_semester = get_current_semester()
            update_current_schedule_from_main(next_week, current_semester)
            
            db.session.commit()
            
            return jsonify({'success': True, 'message': f'Перешли на неделю {next_week}'})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'})

# Вспомогательные функции
def get_current_week():
    setting = AppSettings.query.filter_by(key='current_week').first()
    if setting:
        return int(setting.value)
    else:
        setting = AppSettings(key='current_week', value='1')
        db.session.add(setting)
        db.session.commit()
        return 1

def get_current_semester():
    setting = AppSettings.query.filter_by(key='current_semester').first()
    if setting:
        return int(setting.value)
    else:
        setting = AppSettings(key='current_semester', value='1')
        db.session.add(setting)
        db.session.commit()
        return 1

def update_current_schedule_from_main(week_number, semester):
    ScheduleEntry.query.filter_by(
        week_number=week_number,
        semester=semester
    ).delete()
    
    week_parity = 'even' if week_number % 2 == 0 else 'odd'
    
    main_entries = MainScheduleEntry.query.filter_by(
        semester=semester
    ).filter(
        (MainScheduleEntry.week_parity == 'both') |
        (MainScheduleEntry.week_parity == week_parity)
    ).all()
    
    for main_entry in main_entries:
        schedule_entry = ScheduleEntry(
            group_id=main_entry.group_id,
            subject_id=main_entry.subject_id,
            teacher_id=main_entry.teacher_id,
            room_id=main_entry.room_id,
            day=main_entry.day,
            lesson_number=main_entry.lesson_number,
            week_number=week_number,
            week_parity=main_entry.week_parity,
            semester=semester,
            is_changed=False
        )
        db.session.add(schedule_entry)
    
    db.session.commit()
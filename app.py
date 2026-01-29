import os
import sys
from sqlalchemy import text, and_, or_, not_
from sqlalchemy.orm import joinedload
import random
from datetime import datetime, timedelta
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, jsonify, request, session, send_from_directory
from config import Config
from models import db, User, Teacher, Subject, Group, Room, TeacherSubject, AppSettings, GroupSubject, ScheduleEntry, MainScheduleEntry, AutoFillLog, GroupPractice
from auth import init_auth, login_manager
from flask_login import login_required, current_user, login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
import json


def create_app():
    app = Flask(__name__, static_folder='static', template_folder='pages')
    app.config.from_object(Config)
    app.secret_key = 'your-secret-key-change-in-production'
    
    db.init_app(app)
    init_auth(app)
    
    with app.app_context():
        db.create_all()
        create_admin_user()
        populate_initial_data()
    
    # ========== ОБРАБОТЧИКИ ОШИБОК ==========
    
    @app.errorhandler(500)
    def handle_500(error):
        return jsonify({
            'success': False,
            'message': 'Internal server error',
            'error': str(error) if app.debug else 'Server error'
        }), 500
    
    @app.errorhandler(404)
    def handle_404(error):
        return jsonify({
            'success': False,
            'message': 'Not found'
        }), 404
    
    @app.errorhandler(403)
    def handle_403(error):
        return jsonify({
            'success': False,
            'message': 'Access denied'
        }), 403
    
    # ========== РОУТЫ ДЛЯ HTML СТРАНИЦ ==========
    
    @app.route('/')
    def index():
        return send_from_directory('pages', 'index.html')
    
    @app.route('/admin')
    @login_required
    def admin():
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403
        return send_from_directory('pages', 'admin.html')
    
    @app.route('/schedule')
    def schedule():
        return send_from_directory('pages', 'schedule.html')
    
    @app.route('/current_schedule')
    @login_required
    def current_schedule():
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403
        return send_from_directory('pages', 'current_schedule.html')
    
    @app.route('/group_management')
    @login_required
    def group_management():
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403
        return send_from_directory('pages', 'group_management.html')
    
    @app.route('/login')
    def login_page():
        return send_from_directory('pages', 'login.html')
    
    @app.route('/semester_management')
    @login_required
    def semester_management():
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403
        return send_from_directory('pages', 'semester_management.html')
    
    @app.route('/statistics')
    @login_required
    def statistics_page():
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403
        return send_from_directory('pages', 'statistics.html')
    
    @app.route('/teacher_load')
    @login_required
    def teacher_load_page():
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403
        return send_from_directory('pages', 'teacher_load.html')
    
    # ========== API РОУТЫ ==========
    
    @app.route('/api/login', methods=['POST'])
    def api_login():
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return jsonify({'success': True, 'message': 'Вход выполнен'})
        
        return jsonify({'success': False, 'message': 'Неверные данные'})
    
    @app.route('/api/logout', methods=['POST'])
    @login_required
    def api_logout():
        logout_user()
        return jsonify({'success': True, 'message': 'Выход выполнен'})
    
    @app.route('/api/user_info')
    def api_user_info():
        if current_user.is_authenticated:
            return jsonify({
                'authenticated': True,
                'username': current_user.username,
                'role': current_user.role
            })
        return jsonify({'authenticated': False})
    
    # Основные данные
    @app.route('/api/data/groups')
    def api_get_groups():
        groups = Group.query.order_by(Group.course, Group.name).all()
        return jsonify([{'id': g.id, 'name': g.name, 'course': g.course} for g in groups])
    
    @app.route('/api/data/teachers')
    def api_get_teachers():
        teachers = Teacher.query.order_by(Teacher.name).all()
        return jsonify([{'id': t.id, 'name': t.name} for t in teachers])
    
    @app.route('/api/data/subjects')
    def api_get_subjects():
        subjects = Subject.query.order_by(Subject.name).all()
        return jsonify([{'id': s.id, 'name': s.name} for s in subjects])
    
    @app.route('/api/data/rooms')
    def api_get_rooms():
        rooms = Room.query.order_by(Room.name).all()
        return jsonify([{'id': r.id, 'name': r.name} for r in rooms])
    
    # Добавление группы
    @app.route('/api/data/groups', methods=['POST'])
    @login_required
    def api_add_group():
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        try:
            data = request.get_json()
            name = data.get('name')
            course = data.get('course', 1)
            
            if not name:
                return jsonify({'success': False, 'message': 'Название группы обязательно'})
            
            existing = Group.query.filter_by(name=name).first()
            if existing:
                return jsonify({'success': False, 'message': 'Группа с таким именем уже существует'})
            
            group = Group(name=name, course=course)
            db.session.add(group)
            db.session.commit()
            
            return jsonify({'success': True, 'message': 'Группа добавлена', 'id': group.id})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)})
    
    # Удаление группы
    @app.route('/api/group/delete/<int:id>', methods=['DELETE'])
    @login_required
    def api_delete_group(id):
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        try:
            group = Group.query.get(id)
            if group:
                # Удаляем все связанные записи
                ScheduleEntry.query.filter_by(group_id=group.id).delete()
                MainScheduleEntry.query.filter_by(group_id=group.id).delete()
                GroupSubject.query.filter_by(group_id=group.id).delete()
                GroupPractice.query.filter_by(group_id=group.id).delete()
                
                db.session.delete(group)
                db.session.commit()
                return jsonify({'success': True, 'message': 'Группа удалена'})
            return jsonify({'success': False, 'message': 'Группа не найдена'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)})
    
    # Настройки
    @app.route('/api/settings/current')
    def api_get_current_settings():
        week = AppSettings.query.filter_by(key='current_week').first()
        semester = AppSettings.query.filter_by(key='current_semester').first()
        
        return jsonify({
            'week': int(week.value) if week else 1,
            'semester': int(semester.value) if semester else 1
        })
    
    @app.route('/api/settings/set_week', methods=['POST'])
    @login_required
    def api_set_week():
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        data = request.get_json()
        week = int(data.get('week', 1))
        
        setting = AppSettings.query.filter_by(key='current_week').first()
        if setting:
            setting.value = str(week)
        else:
            setting = AppSettings(key='current_week', value=str(week))
            db.session.add(setting)
        
        db.session.commit()
        return jsonify({'success': True, 'message': f'Установлена неделя {week}'})
    
    @app.route('/api/settings/set_semester', methods=['POST'])
    @login_required
    def api_set_semester():
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        data = request.get_json()
        semester = int(data.get('semester', 1))
        
        setting = AppSettings.query.filter_by(key='current_semester').first()
        if setting:
            setting.value = str(semester)
        else:
            setting = AppSettings(key='current_semester', value=str(semester))
            db.session.add(setting)
        
        db.session.commit()
        return jsonify({'success': True, 'message': f'Установлен семестр {semester}'})
    
    # Текущее расписание
    @app.route('/api/schedule/current')
    def api_get_current_schedule():
        week = request.args.get('week', type=int, default=1)
        semester = request.args.get('semester', type=int, default=1)
        day = request.args.get('day', 'Понедельник')
        
        entries = ScheduleEntry.query.filter_by(
            day=day,
            week_number=week,
            semester=semester
        ).all()
        
        result = []
        for entry in entries:
            pair_num = get_pair_number_by_lesson(entry.day, entry.lesson_number)
            result.append({
                'id': entry.id,
                'group': entry.group.name,
                'subject': entry.subject.name,
                'teacher': entry.teacher.name,
                'room': entry.room.name,
                'day': entry.day,
                'lesson_number': entry.lesson_number,
                'pair': pair_num,
                'time': get_lesson_time(entry.day, entry.lesson_number),
                'is_changed': entry.is_changed
            })
        
        return jsonify(result)
    
    @app.route('/api/schedule/main')
    def api_get_main_schedule():
        semester = request.args.get('semester', type=int, default=1)
        day = request.args.get('day', 'Понедельник')
        week_parity = request.args.get('week_parity', 'both')
        
        query = MainScheduleEntry.query.filter_by(
            day=day,
            semester=semester
        )
        
        if week_parity != 'both':
            query = query.filter(
                (MainScheduleEntry.week_parity == week_parity) |
                (MainScheduleEntry.week_parity == 'both')
            )
        
        entries = query.all()
        
        result = []
        for entry in entries:
            pair_num = get_pair_number_by_lesson(entry.day, entry.lesson_number)
            result.append({
                'id': entry.id,
                'group': entry.group.name,
                'subject': entry.subject.name,
                'teacher': entry.teacher.name,
                'room': entry.room.name,
                'day': entry.day,
                'lesson_number': entry.lesson_number,
                'pair': pair_num,
                'time': get_lesson_time(entry.day, entry.lesson_number),
                'week_parity': entry.week_parity
            })
        
        return jsonify(result)
    
    @app.route('/api/schedule/add', methods=['POST'])
    @login_required
    def api_add_schedule():
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        try:
            data = request.get_json()
            is_main = data.get('is_main', False)
            
            group = Group.query.filter_by(name=data['group']).first()
            subject = Subject.query.filter_by(name=data['subject']).first()
            teacher = Teacher.query.filter_by(name=data['teacher']).first()
            room = Room.query.filter_by(name=data['room']).first()
            
            if not all([group, subject, teacher, room]):
                return jsonify({'success': False, 'message': 'Не найдены объекты'})
            
            day = data['day']
            lesson_number = int(data['lesson_number'])
            
            if day in ["Понедельник", "Четверг"] and lesson_number == 0 and subject.name != "Разговоры о важном":
                return jsonify({'success': False, 'message': 'На 0 урок можно поставить только "Разговоры о важном"'})
            
            if is_main:
                conflict = MainScheduleEntry.query.filter_by(
                    group_id=group.id,
                    day=data['day'],
                    lesson_number=data['lesson_number'],
                    semester=int(data.get('semester', 1))
                ).first()
            else:
                conflict = ScheduleEntry.query.filter_by(
                    group_id=group.id,
                    day=data['day'],
                    lesson_number=data['lesson_number'],
                    week_number=int(data.get('week', 1)),
                    semester=int(data.get('semester', 1))
                ).first()
            
            if conflict:
                return jsonify({'success': False, 'message': 'Конфликт расписания'})
            
            if is_main:
                entry = MainScheduleEntry(
                    group_id=group.id,
                    subject_id=subject.id,
                    teacher_id=teacher.id,
                    room_id=room.id,
                    day=data['day'],
                    lesson_number=data['lesson_number'],
                    week_parity=data.get('week_parity', 'both'),
                    semester=int(data.get('semester', 1))
                )
            else:
                entry = ScheduleEntry(
                    group_id=group.id,
                    subject_id=subject.id,
                    teacher_id=teacher.id,
                    room_id=room.id,
                    day=data['day'],
                    lesson_number=data['lesson_number'],
                    week_number=int(data.get('week', 1)),
                    semester=int(data.get('semester', 1)),
                    is_changed=True
                )
            
            db.session.add(entry)
            db.session.commit()
            
            return jsonify({'success': True, 'message': 'Добавлено', 'id': entry.id})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/schedule/delete/<int:id>', methods=['DELETE'])
    @login_required
    def api_delete_schedule(id):
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        try:
            entry = ScheduleEntry.query.get(id)
            if entry:
                db.session.delete(entry)
                db.session.commit()
                return jsonify({'success': True, 'message': 'Удалено'})
            return jsonify({'success': False, 'message': 'Не найдено'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/schedule/main/delete/<int:id>', methods=['DELETE'])
    @login_required
    def api_delete_main_schedule(id):
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        try:
            entry = MainScheduleEntry.query.get(id)
            if entry:
                db.session.delete(entry)
                db.session.commit()
                return jsonify({'success': True, 'message': 'Удалено'})
            return jsonify({'success': False, 'message': 'Не найдено'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/schedule/update/<int:id>', methods=['PUT'])
    @login_required
    def api_update_schedule(id):
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        try:
            data = request.get_json()
            entry = ScheduleEntry.query.get(id)
            
            if not entry:
                return jsonify({'success': False, 'message': 'Запись не найдена'})
            
            if 'subject' in data:
                subject = Subject.query.filter_by(name=data['subject']).first()
                if subject:
                    entry.subject_id = subject.id
            
            if 'teacher' in data:
                teacher = Teacher.query.filter_by(name=data['teacher']).first()
                if teacher:
                    entry.teacher_id = teacher.id
            
            if 'room' in data:
                room = Room.query.filter_by(name=data['room']).first()
                if room:
                    entry.room_id = room.id
            
            entry.is_changed = True
            db.session.commit()
            
            return jsonify({'success': True, 'message': 'Обновлено'})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)})
    
    # Управление группами - получение предметов группы
    @app.route('/api/group/<int:group_id>/subjects')
    @login_required
    def api_get_group_subjects(group_id):
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        try:
            group = Group.query.get_or_404(group_id)
            subjects = GroupSubject.query.filter_by(group_id=group_id).all()
            
            result = []
            for gs in subjects:
                result.append({
                    'id': gs.id,
                    'subject_id': gs.subject_id,
                    'subject_name': gs.subject.name,
                    'teacher_id': gs.teacher_id,
                    'teacher_name': gs.teacher.name if gs.teacher else None,
                    'hours_per_week': gs.hours_per_week,
                    'total_hours_semester1': gs.total_hours_semester1 or 0,
                    'total_hours_semester2': gs.total_hours_semester2 or 0
                })
            
            # Получаем информацию о практике
            practice = GroupPractice.query.filter_by(group_id=group_id).first()
            practice_info = {
                'has_practice': bool(practice),
                'day': practice.day if practice else None,
                'subject_id': practice.subject_id if practice else None,
                'subject_name': practice.subject.name if practice and practice.subject else None,
                'teacher_id': practice.teacher_id if practice else None,
                'teacher_name': practice.teacher.name if practice and practice.teacher else None,
                'room_id': practice.room_id if practice else None,
                'room_name': practice.room.name if practice and practice.room else None
            }
            
            return jsonify({
                'success': True,
                'group_id': group.id,
                'group_name': group.name,
                'course': group.course,
                'subjects': result,
                'practice': practice_info
            })
            
        except Exception as e:
            app.logger.error(f'Ошибка загрузки предметов: {str(e)}')
            return jsonify({'success': False, 'message': f'Ошибка загрузки предметов: {str(e)}'})
    
    # НОВЫЙ эндпоинт для добавления предмета группе
    @app.route('/api/group/<int:group_id>/add-subject', methods=['POST'])
    @login_required
    def api_add_subject_to_group(group_id):
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        try:
            data = request.get_json()
            subject_id = data.get('subject_id')
            teacher_id = data.get('teacher_id')
            hours_per_week = data.get('hours_per_week', 0)
            total_hours_semester1 = data.get('total_hours_semester1', 0)
            total_hours_semester2 = data.get('total_hours_semester2', 0)
            
            if not subject_id:
                return jsonify({'success': False, 'message': 'Предмет обязателен'})
            
            # Проверяем существование
            group = Group.query.get(group_id)
            subject = Subject.query.get(subject_id)
            
            if not group or not subject:
                return jsonify({'success': False, 'message': 'Группа или предмет не найдены'})
            
            existing = GroupSubject.query.filter_by(
                group_id=group_id,
                subject_id=subject_id
            ).first()
            
            if existing:
                # Обновляем существующую запись
                existing.teacher_id = teacher_id
                existing.hours_per_week = hours_per_week
                existing.total_hours_semester1 = total_hours_semester1
                existing.total_hours_semester2 = total_hours_semester2
            else:
                # Создаем новую запись
                gs = GroupSubject(
                    group_id=group_id,
                    subject_id=subject_id,
                    teacher_id=teacher_id,
                    hours_per_week=hours_per_week,
                    total_hours_semester1=total_hours_semester1,
                    total_hours_semester2=total_hours_semester2
                )
                db.session.add(gs)
            
            db.session.commit()
            return jsonify({'success': True, 'message': 'Предмет добавлен к группе'})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)})
    
    # Эндпоинт для обновления часов в неделю
    @app.route('/api/group/subject/<int:id>/hours', methods=['PUT'])
    @login_required
    def api_update_group_subject_hours_single(id):
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        try:
            data = request.get_json()
            hours_per_week = data.get('hours_per_week', 0)
            
            gs = GroupSubject.query.get(id)
            if not gs:
                return jsonify({'success': False, 'message': 'Запись не найдена'})
            
            gs.hours_per_week = hours_per_week
            db.session.commit()
            
            return jsonify({'success': True, 'message': 'Часы обновлены'})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)})
    
    # Эндпоинт для обновления часов за семестр
    @app.route('/api/group/subject/<int:id>/semester-hours', methods=['PUT'])
    @login_required
    def api_update_group_subject_semester_hours(id):
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        try:
            data = request.get_json()
            total_hours_semester1 = data.get('total_hours_semester1')
            total_hours_semester2 = data.get('total_hours_semester2')
            
            gs = GroupSubject.query.get(id)
            if not gs:
                return jsonify({'success': False, 'message': 'Запись не найдена'})
            
            if total_hours_semester1 is not None:
                gs.total_hours_semester1 = total_hours_semester1
            if total_hours_semester2 is not None:
                gs.total_hours_semester2 = total_hours_semester2
            
            db.session.commit()
            
            return jsonify({'success': True, 'message': 'Часы обновлены'})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/group/subject/add', methods=['POST'])
    @login_required
    def api_add_group_subject():
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        try:
            data = request.get_json()
            group_id = data['group_id']
            subject_id = data['subject_id']
            teacher_id = data.get('teacher_id')
            hours_per_week = data.get('hours_per_week', 0)
            total_hours_semester1 = data.get('total_hours_semester1', 0)
            total_hours_semester2 = data.get('total_hours_semester2', 0)
            
            existing = GroupSubject.query.filter_by(
                group_id=group_id,
                subject_id=subject_id
            ).first()
            
            if existing:
                existing.teacher_id = teacher_id
                existing.hours_per_week = hours_per_week
                existing.total_hours_semester1 = total_hours_semester1
                existing.total_hours_semester2 = total_hours_semester2
            else:
                gs = GroupSubject(
                    group_id=group_id,
                    subject_id=subject_id,
                    teacher_id=teacher_id,
                    hours_per_week=hours_per_week,
                    total_hours_semester1=total_hours_semester1,
                    total_hours_semester2=total_hours_semester2
                )
                db.session.add(gs)
            
            db.session.commit()
            return jsonify({'success': True, 'message': 'Сохранено'})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/group/subject/delete/<int:id>', methods=['DELETE'])
    @login_required
    def api_delete_group_subject(id):
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        try:
            gs = GroupSubject.query.get(id)
            if gs:
                db.session.delete(gs)
                db.session.commit()
                return jsonify({'success': True, 'message': 'Удалено'})
            return jsonify({'success': False, 'message': 'Не найдено'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)})
    
    
    @app.route('/api/group/subject/update_hours/<int:id>', methods=['PUT'])
    @login_required
    def api_update_group_subject_hours(id):
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        try:
            data = request.get_json()
            hours_per_week = data.get('hours_per_week', 0)
            total_hours_semester1 = data.get('total_hours_semester1', 0)
            total_hours_semester2 = data.get('total_hours_semester2', 0)
            
            gs = GroupSubject.query.get(id)
            if not gs:
                return jsonify({'success': False, 'message': 'Запись не найдена'})
            
            gs.hours_per_week = hours_per_week
            gs.total_hours_semester1 = total_hours_semester1
            gs.total_hours_semester2 = total_hours_semester2
            
            db.session.commit()
            
            return jsonify({'success': True, 'message': 'Часы обновлены'})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)})
    
    # Практика - получение информации
    @app.route('/api/group/<int:group_id>/practice')
    @login_required
    def api_get_group_practice(group_id):
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        try:
            practice = GroupPractice.query.filter_by(group_id=group_id).first()
            
            if practice:
                return jsonify({
                    'success': True,
                    'practice': {
                        'day': practice.day,
                        'subject_id': practice.subject_id,
                        'subject_name': practice.subject.name if practice.subject else None,
                        'teacher_id': practice.teacher_id,
                        'teacher_name': practice.teacher.name if practice.teacher else None,
                        'room_id': practice.room_id,
                        'room_name': practice.room.name if practice.room else None
                    }
                })
            else:
                return jsonify({
                    'success': True,
                    'practice': None
                })
                
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})
    
    # Добавление/обновление практики для группы
    @app.route('/api/group/practice', methods=['POST'])
    @login_required
    def api_set_group_practice():
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        try:
            data = request.get_json()
            group_id = data.get('group_id')
            day = data.get('day')
            subject_id = data.get('subject_id')
            teacher_id = data.get('teacher_id')
            room_id = data.get('room_id')
            
            if not group_id or not day:
                return jsonify({'success': False, 'message': 'Группа и день обязательны'})
            
            practice = GroupPractice.query.filter_by(group_id=group_id).first()
            
            if practice:
                practice.day = day
                practice.subject_id = subject_id
                practice.teacher_id = teacher_id
                practice.room_id = room_id
            else:
                practice = GroupPractice(
                    group_id=group_id,
                    day=day,
                    subject_id=subject_id,
                    teacher_id=teacher_id,
                    room_id=room_id
                )
                db.session.add(practice)
            
            db.session.commit()
            return jsonify({'success': True, 'message': 'Практика назначена'})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/group/practice/delete/<int:group_id>', methods=['DELETE'])
    @login_required
    def api_delete_group_practice(group_id):
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        try:
            practice = GroupPractice.query.filter_by(group_id=group_id).first()
            if practice:
                db.session.delete(practice)
                db.session.commit()
                return jsonify({'success': True, 'message': 'Практика удалена'})
            return jsonify({'success': False, 'message': 'Практика не найдена'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)})
    
    # Статистика автозаполнения
    @app.route('/api/schedule/autofill-stats')
    @login_required
    def api_get_autofill_stats():
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        try:
            # Подсчитываем общую статистику
            total_groups = Group.query.count()
            
            # Подсчитываем общее количество часов в неделю
            group_subjects = GroupSubject.query.all()
            total_hours = sum(gs.hours_per_week for gs in group_subjects)
            
            # Подсчитываем конфликты в текущем расписании
            current_week = get_current_week()
            current_semester = get_current_semester()
            conflicts = check_schedule_conflicts(current_week, current_semester)
            total_conflicts = len(conflicts)
            
            return jsonify({
                'success': True,
                'stats': {
                    'total_groups': total_groups,
                    'total_hours': total_hours,
                    'total_conflicts': total_conflicts
                }
            })
            
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})
    
    # Автозаполнение расписания
    @app.route('/api/schedule/autofill', methods=['POST'])
    @login_required
    def api_autofill_schedule():
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        try:
            data = request.get_json()
            week = data.get('week', get_current_week())
            semester = data.get('semester', get_current_semester())
            fill_type = data.get('type', 'both')
            
            result = auto_fill_schedule(week, semester, fill_type)
            
            return jsonify({
                'success': True,
                'message': 'Расписание успешно заполнено',
                'created_entries': result.get('entries_added', 0),
                'conflicts': result.get('conflicts', 0),
                'errors': result.get('errors', 0)
            })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)})
    
    # Статистика
    @app.route('/api/statistics')
    @login_required
    def api_get_statistics():
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        week = request.args.get('week', type=int, default=1)
        semester = request.args.get('semester', type=int, default=1)
        
        groups = Group.query.all()
        group_stats = []
        
        for group in groups:
            entries = ScheduleEntry.query.filter_by(
                group_id=group.id,
                week_number=week,
                semester=semester
            ).all()
            
            changed = sum(1 for e in entries if e.is_changed)
            main = len(entries) - changed
            
            group_subjects = GroupSubject.query.filter_by(group_id=group.id).all()
            total_hours = sum(gs.hours_per_week for gs in group_subjects)
            completed_hours = len(entries) * 2
            remaining_hours = max(0, total_hours - completed_hours)
            
            group_stats.append({
                'group_name': group.name,
                'course': group.course,
                'total_lessons': len(entries),
                'changed_lessons': changed,
                'main_lessons': main,
                'total_hours': total_hours,
                'completed_hours': completed_hours,
                'remaining_hours': remaining_hours,
                'progress': int((completed_hours / total_hours) * 100) if total_hours > 0 else 0
            })
        
        teachers = Teacher.query.all()
        teacher_stats = []
        
        for teacher in teachers:
            entries = ScheduleEntry.query.filter_by(
                teacher_id=teacher.id,
                week_number=week,
                semester=semester
            ).all()
            
            teacher_stats.append({
                'teacher_name': teacher.name,
                'total_lessons': len(entries)
            })
        
        total_lessons = sum(g['total_lessons'] for g in group_stats)
        total_completed_hours = sum(g['completed_hours'] for g in group_stats)
        total_remaining_hours = sum(g['remaining_hours'] for g in group_stats)
        
        return jsonify({
            'week': week,
            'semester': semester,
            'total_lessons': total_lessons,
            'total_completed_hours': total_completed_hours,
            'total_remaining_hours': total_remaining_hours,
            'group_stats': group_stats,
            'teacher_stats': teacher_stats
        })
    
    # Полная статистика
    @app.route('/api/statistics/full')
    @login_required
    def api_get_full_statistics():
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        week = request.args.get('week', type=int, default=1)
        semester = request.args.get('semester', type=int, default=1)
        
        groups = Group.query.all()
        group_stats = []
        
        for group in groups:
            entries = ScheduleEntry.query.filter_by(
                group_id=group.id,
                week_number=week,
                semester=semester
            ).all()
            
            changed = sum(1 for e in entries if e.is_changed)
            main = len(entries) - changed
            
            group_subjects = GroupSubject.query.filter_by(group_id=group.id).all()
            total_hours = sum(gs.hours_per_week for gs in group_subjects)
            completed_hours = len(entries) * 2
            remaining_hours = max(0, total_hours - completed_hours)
            
            subjects_detail = []
            for gs in group_subjects:
                subjects_detail.append({
                    'subject_name': gs.subject.name,
                    'teacher_name': gs.teacher.name if gs.teacher else 'Не назначен',
                    'hours_per_week': gs.hours_per_week,
                    'total_hours_semester1': gs.total_hours_semester1 or 0,
                    'total_hours_semester2': gs.total_hours_semester2 or 0
                })
            
            group_stats.append({
                'group_name': group.name,
                'course': group.course,
                'total_lessons': len(entries),
                'changed_lessons': changed,
                'main_lessons': main,
                'total_hours': total_hours,
                'completed_hours': completed_hours,
                'remaining_hours': remaining_hours,
                'progress': int((completed_hours / total_hours) * 100) if total_hours > 0 else 0,
                'subjects': subjects_detail
            })
        
        teachers = Teacher.query.all()
        teacher_stats = []
        
        for teacher in teachers:
            entries = ScheduleEntry.query.filter_by(
                teacher_id=teacher.id,
                week_number=week,
                semester=semester
            ).all()
            
            teacher_subjects = GroupSubject.query.filter_by(teacher_id=teacher.id).all()
            total_hours = sum(ts.hours_per_week for ts in teacher_subjects)
            
            groups_detail = []
            for ts in teacher_subjects:
                groups_detail.append({
                    'group_name': ts.group.name,
                    'subject_name': ts.subject.name,
                    'hours_per_week': ts.hours_per_week
                })
            
            teacher_stats.append({
                'teacher_name': teacher.name,
                'total_lessons': len(entries),
                'total_hours': total_hours,
                'groups': groups_detail
            })
        
        total_groups_hours = sum(g['total_hours'] for g in group_stats)
        total_teachers_hours = sum(t['total_hours'] for t in teacher_stats)
        total_completed_hours = sum(g['completed_hours'] for g in group_stats)
        total_remaining_hours = sum(g['remaining_hours'] for g in group_stats)
        
        return jsonify({
            'success': True,
            'week': week,
            'semester': semester,
            'total_groups_hours': total_groups_hours,
            'total_teachers_hours': total_teachers_hours,
            'total_completed_hours': total_completed_hours,
            'total_remaining_hours': total_remaining_hours,
            'group_stats': group_stats,
            'teacher_stats': teacher_stats
        })
    
    # Логи автозаполнения
    @app.route('/api/autofill/logs')
    @login_required
    def api_get_autofill_logs():
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        logs = AutoFillLog.query.order_by(AutoFillLog.created_at.desc()).limit(50).all()
        
        result = []
        for log in logs:
            result.append({
                'id': log.id,
                'week': log.week_number,
                'semester': log.semester,
                'type': log.fill_type,
                'entries_added': log.entries_added,
                'conflicts': log.conflicts,
                'errors': log.errors,
                'created_at': log.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        return jsonify({'success': True, 'logs': result})
    
    @app.route('/api/pairs/<day>')
    def api_get_pairs_for_day(day):
        pairs = get_available_pairs_for_day(day)
        result = []
        
        for pair_num in pairs:
            result.append({
                'pair': pair_num,
                'name': get_pair_name(pair_num),
                'lessons': get_lessons_in_pair(day, pair_num),
                'time': get_pair_time(day, pair_num)
            })
        
        return jsonify(result)
    
    @app.route('/api/pair/<day>/<int:pair>/lessons')
    def api_get_lessons_in_pair(day, pair):
        lessons = get_lessons_in_pair(day, pair)
        result = []
        
        for lesson_num in lessons:
            result.append({
                'lesson': lesson_num,
                'time': get_lesson_time(day, lesson_num)
            })
        
        return jsonify(result)
    
    @app.route('/api/next_week', methods=['POST'])
    @login_required
    def api_next_week():
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
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/clear_week', methods=['POST'])
    @login_required
    def api_clear_week():
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        try:
            current_week = get_current_week()
            current_semester = get_current_semester()
            
            ScheduleEntry.query.filter_by(
                week_number=current_week,
                semester=current_semester
            ).delete()
            
            update_current_schedule_from_main(current_week, current_semester)
            
            db.session.commit()
            return jsonify({'success': True, 'message': f'Неделя {current_week} очищена и заполнена из основного расписания'})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/next_semester', methods=['POST'])
    @login_required
    def api_next_semester():
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        try:
            current_semester = get_current_semester()
            next_semester = 2 if current_semester == 1 else 1
            
            setting = AppSettings.query.filter_by(key='current_semester').first()
            if setting:
                setting.value = str(next_semester)
            else:
                setting = AppSettings(key='current_semester', value=str(next_semester))
                db.session.add(setting)
            
            week_setting = AppSettings.query.filter_by(key='current_week').first()
            if week_setting:
                week_setting.value = '1'
            else:
                week_setting = AppSettings(key='current_week', value='1')
                db.session.add(week_setting)
            
            ScheduleEntry.query.filter_by(semester=next_semester).delete()
            
            db.session.commit()
            return jsonify({'success': True, 'message': f'Перешли на {next_semester} семестр'})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/semester_stats')
    @login_required
    def api_get_semester_stats():
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        try:
            semester_stats = {}
            
            for semester in [1, 2]:
                total_entries = ScheduleEntry.query.filter_by(semester=semester).count()
                main_entries = MainScheduleEntry.query.filter_by(semester=semester).count()
                
                semester_stats[semester] = {
                    'name': 'Осенний семестр' if semester == 1 else 'Весенний семестр',
                    'entries_count': total_entries,
                    'main_entries_count': main_entries,
                    'weeks': 52
                }
            
            current_week = get_current_week()
            current_semester = get_current_semester()
            
            return jsonify({
                'current_week': current_week,
                'current_semester': current_semester,
                'semester_stats': semester_stats,
                'max_weeks': 52
            })
            
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/teacher_load')
    @login_required
    def api_get_teacher_load():
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        try:
            teacher_load = []
            
            teachers = Teacher.query.all()
            for teacher in teachers:
                total_pairs = ScheduleEntry.query.filter_by(teacher_id=teacher.id).count()
                
                teacher_load.append({
                    'teacher_id': teacher.id,
                    'teacher_name': teacher.name,
                    'total_pairs': total_pairs,
                    'total_hours': total_pairs * 2
                })
            
            return jsonify({
                'success': True,
                'teacher_load': teacher_load
            })
            
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/schedule/check_conflicts')
    @login_required
    def api_check_conflicts():
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'Доступ запрещен'})
        
        try:
            week = request.args.get('week', type=int, default=get_current_week())
            semester = request.args.get('semester', type=int, default=get_current_semester())
            
            conflicts = check_schedule_conflicts(week, semester)
            
            return jsonify({
                'success': True,
                'conflicts': conflicts,
                'has_conflicts': len(conflicts) > 0
            })
            
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})
    
    return app

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def get_pair_number_by_lesson(day, lesson_number):
    if lesson_number == 0:
        return 0
    elif day == "Суббота":
        if lesson_number in [1, 2]:
            return 1
        elif lesson_number in [3, 4]:
            return 2
        elif lesson_number in [5, 6]:
            return 3
        elif lesson_number in [7, 8]:
            return 4
    else:
        if lesson_number in [1, 2]:
            return 1
        elif lesson_number in [3, 4]:
            return 2
        elif lesson_number in [5, 6]:
            return 3
        elif lesson_number in [7, 8]:
            return 4
        elif lesson_number in [9, 10]:
            return 5
        elif lesson_number in [11, 12]:
            return 6
    return 0

def get_available_pairs_for_day(day):
    if day == "Суббота":
        return [1, 2, 3, 4]
    elif day in ["Понедельник", "Четверг"]:
        return [0, 1, 2, 3, 4, 5, 6]
    else:
        return [1, 2, 3, 4, 5, 6]

def get_lessons_in_pair(day, pair):
    if pair == 0:
        return [0]
    elif pair == 1:
        return [1, 2]
    elif pair == 2:
        return [3, 4]
    elif pair == 3:
        return [5, 6]
    elif pair == 4:
        return [7, 8]
    elif pair == 5:
        return [9, 10]
    elif pair == 6:
        return [11, 12]
    return []

def get_pair_name(pair):
    return f"Пара {pair}"

def get_pair_time(day, pair):
    if pair == 0:
        return "8:30-9:10"
    elif pair == 1:
        if day == "Суббота":
            return "8:00-9:25"
        elif day in ["Понедельник", "Четверг"]:
            return "9:15-10:40"
        else:
            return "8:30-9:55"
    elif pair == 2:
        if day == "Суббота":
            return "9:30-10:55"
        elif day in ["Понедельник", "Четверг"]:
            return "11:20-12:45"
        else:
            return "10:35-12:00"
    elif pair == 3:
        if day == "Суббота":
            return "11:00-12:25"
        elif day in ["Понедельник", "Четверг"]:
            return "13:25-14:50"
        else:
            return "12:40-14:05"
    elif pair == 4:
        if day == "Суббота":
            return "12:30-13:55"
        elif day in ["Понедельник", "Четверг"]:
            return "15:00-16:25"
        else:
            return "14:15-15:40"
    elif pair == 5:
        if day in ["Понедельник", "Четверг"]:
            return "16:30-17:55"
        else:
            return "15:45-17:10"
    elif pair == 6:
        if day in ["Понедельник", "Четверг"]:
            return "18:00-19:25"
        else:
            return "17:15-18:40"
    return ""

def get_lesson_time(day, lesson_number):
    pair = get_pair_number_by_lesson(day, lesson_number)
    return get_pair_time(day, pair)

def get_current_week():
    setting = AppSettings.query.filter_by(key='current_week').first()
    if setting:
        return int(setting.value)
    return 1

def get_current_semester():
    setting = AppSettings.query.filter_by(key='current_semester').first()
    if setting:
        return int(setting.value)
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

def check_schedule_conflicts(week, semester):
    conflicts = []
    
    entries = ScheduleEntry.query.filter_by(
        week_number=week,
        semester=semester
    ).all()
    
    teacher_conflicts = {}
    for entry in entries:
        key = (entry.day, entry.lesson_number, entry.teacher_id)
        if key not in teacher_conflicts:
            teacher_conflicts[key] = []
        teacher_conflicts[key].append(entry)
    
    for key, entries_list in teacher_conflicts.items():
        if len(entries_list) > 1:
            conflicts.append({
                'type': 'teacher_conflict',
                'day': key[0],
                'lesson_number': key[1],
                'teacher': entries_list[0].teacher.name,
                'groups': [e.group.name for e in entries_list],
                'message': f'Преподаватель {entries_list[0].teacher.name} ведет одновременно в группах: {", ".join([e.group.name for e in entries_list])}'
            })
    
    group_conflicts = {}
    for entry in entries:
        key = (entry.day, entry.lesson_number, entry.group_id)
        if key not in group_conflicts:
            group_conflicts[key] = []
        group_conflicts[key].append(entry)
    
    for key, entries_list in group_conflicts.items():
        if len(entries_list) > 1:
            conflicts.append({
                'type': 'group_conflict',
                'day': key[0],
                'lesson_number': key[1],
                'group': entries_list[0].group.name,
                'subjects': [e.subject.name for e in entries_list],
                'message': f'Группа {entries_list[0].group.name} имеет {len(entries_list)} занятия одновременно'
            })
    
    room_conflicts = {}
    for entry in entries:
        key = (entry.day, entry.lesson_number, entry.room_id)
        if key not in room_conflicts:
            room_conflicts[key] = []
        room_conflicts[key].append(entry)
    
    for key, entries_list in room_conflicts.items():
        if len(entries_list) > 1:
            conflicts.append({
                'type': 'room_conflict',
                'day': key[0],
                'lesson_number': key[1],
                'room': entries_list[0].room.name,
                'groups': [e.group.name for e in entries_list],
                'message': f'Аудитория {entries_list[0].room.name} занята {len(entries_list)} группами одновременно'
            })
    
    return conflicts

def auto_fill_schedule(week, semester, fill_type='both'):
    log_entry = AutoFillLog(
        week_number=week,
        semester=semester,
        fill_type=fill_type,
        entries_added=0,
        conflicts=0,
        errors=0
    )
    db.session.add(log_entry)
    
    try:
        if fill_type in ['current', 'both']:
            ScheduleEntry.query.filter_by(
                week_number=week,
                semester=semester
            ).delete()
        
        if fill_type in ['main', 'both']:
            MainScheduleEntry.query.filter_by(semester=semester).delete()
        
        groups = Group.query.order_by(Group.course, Group.name).all()
        days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"]
        
        for group in groups:
            group_subjects = GroupSubject.query.filter_by(group_id=group.id).all()
            practice = GroupPractice.query.filter_by(group_id=group.id).first()
            
            subjects_to_schedule = []
            for gs in group_subjects:
                for _ in range(gs.hours_per_week // 2):
                    subjects_to_schedule.append({
                        'subject_id': gs.subject_id,
                        'teacher_id': gs.teacher_id,
                        'subject_name': gs.subject.name,
                        'teacher_name': gs.teacher.name if gs.teacher else None
                    })
            
            random.shuffle(subjects_to_schedule)
            
            current_day_index = 0
            current_lesson = 0
            
            if practice and practice.day in days:
                practice_day_index = days.index(practice.day)
                max_pairs = 4 if group.course >= 2 else 2
                
                for pair in range(1, max_pairs + 1):
                    lessons = get_lessons_in_pair(practice.day, pair)
                    for lesson in lessons:
                        if can_schedule_lesson(
                            group.id, practice.subject_id, practice.teacher_id, practice.room_id,
                            practice.day, lesson, week, semester, fill_type
                        ):
                            if fill_type in ['main', 'both']:
                                entry = MainScheduleEntry(
                                    group_id=group.id,
                                    subject_id=practice.subject_id,
                                    teacher_id=practice.teacher_id,
                                    room_id=practice.room_id,
                                    day=practice.day,
                                    lesson_number=lesson,
                                    week_parity='both',
                                    semester=semester
                                )
                                db.session.add(entry)
                            
                            if fill_type in ['current', 'both']:
                                entry = ScheduleEntry(
                                    group_id=group.id,
                                    subject_id=practice.subject_id,
                                    teacher_id=practice.teacher_id,
                                    room_id=practice.room_id,
                                    day=practice.day,
                                    lesson_number=lesson,
                                    week_number=week,
                                    semester=semester,
                                    is_changed=False
                                )
                                db.session.add(entry)
                            
                            log_entry.entries_added += 1
            
            for subject_data in subjects_to_schedule:
                placed = False
                attempts = 0
                max_attempts = len(days) * 10
                
                while not placed and attempts < max_attempts:
                    day = days[current_day_index % len(days)]
                    
                    if practice and group.course >= 2 and day == practice.day:
                        current_day_index += 1
                        attempts += 1
                        continue
                    
                    available_pairs = get_available_pairs_for_day(day)
                    
                    if day in ["Понедельник", "Четверг"] and subject_data['subject_name'] == "Разговоры о важном":
                        lesson = 0
                    else:
                        pair = random.choice(available_pairs)
                        if pair == 0:
                            current_day_index += 1
                            attempts += 1
                            continue
                        
                        lessons = get_lessons_in_pair(day, pair)
                        lesson = random.choice(lessons)
                    
                    room = get_available_room(day, lesson, week, semester, fill_type)
                    
                    if room and subject_data['teacher_id']:
                        if can_schedule_lesson(
                            group.id, subject_data['subject_id'], subject_data['teacher_id'], room.id,
                            day, lesson, week, semester, fill_type
                        ):
                            if fill_type in ['main', 'both']:
                                entry = MainScheduleEntry(
                                    group_id=group.id,
                                    subject_id=subject_data['subject_id'],
                                    teacher_id=subject_data['teacher_id'],
                                    room_id=room.id,
                                    day=day,
                                    lesson_number=lesson,
                                    week_parity='both',
                                    semester=semester
                                )
                                db.session.add(entry)
                            
                            if fill_type in ['current', 'both']:
                                entry = ScheduleEntry(
                                    group_id=group.id,
                                    subject_id=subject_data['subject_id'],
                                    teacher_id=subject_data['teacher_id'],
                                    room_id=room.id,
                                    day=day,
                                    lesson_number=lesson,
                                    week_number=week,
                                    semester=semester,
                                    is_changed=False
                                )
                                db.session.add(entry)
                            
                            log_entry.entries_added += 1
                            placed = True
                    
                    current_day_index += 1
                    attempts += 1
                
                if not placed:
                    log_entry.errors += 1
        
        db.session.commit()
        
        conflicts = check_schedule_conflicts(week, semester)
        log_entry.conflicts = len(conflicts)
        
        db.session.commit()
        
        return {
            'entries_added': log_entry.entries_added,
            'conflicts': len(conflicts),
            'errors': log_entry.errors,
            'has_conflicts': len(conflicts) > 0
        }
        
    except Exception as e:
        db.session.rollback()
        log_entry.errors += 1
        db.session.commit()
        raise e

def can_schedule_lesson(group_id, subject_id, teacher_id, room_id, day, lesson, week, semester, fill_type):
    if fill_type in ['main', 'both']:
        conflict = MainScheduleEntry.query.filter(
            or_(
                and_(
                    MainScheduleEntry.group_id == group_id,
                    MainScheduleEntry.day == day,
                    MainScheduleEntry.lesson_number == lesson,
                    MainScheduleEntry.semester == semester
                ),
                and_(
                    MainScheduleEntry.teacher_id == teacher_id,
                    MainScheduleEntry.day == day,
                    MainScheduleEntry.lesson_number == lesson,
                    MainScheduleEntry.semester == semester
                ),
                and_(
                    MainScheduleEntry.room_id == room_id,
                    MainScheduleEntry.day == day,
                    MainScheduleEntry.lesson_number == lesson,
                    MainScheduleEntry.semester == semester
                )
            )
        ).first()
        
        if conflict:
            return False
    
    if fill_type in ['current', 'both']:
        conflict = ScheduleEntry.query.filter(
            or_(
                and_(
                    ScheduleEntry.group_id == group_id,
                    ScheduleEntry.day == day,
                    ScheduleEntry.lesson_number == lesson,
                    ScheduleEntry.week_number == week,
                    ScheduleEntry.semester == semester
                ),
                and_(
                    ScheduleEntry.teacher_id == teacher_id,
                    ScheduleEntry.day == day,
                    ScheduleEntry.lesson_number == lesson,
                    ScheduleEntry.week_number == week,
                    ScheduleEntry.semester == semester
                ),
                and_(
                    ScheduleEntry.room_id == room_id,
                    ScheduleEntry.day == day,
                    ScheduleEntry.lesson_number == lesson,
                    ScheduleEntry.week_number == week,
                    ScheduleEntry.semester == semester
                )
            )
        ).first()
        
        if conflict:
            return False
    
    return True

def get_available_room(day, lesson, week, semester, fill_type):
    rooms = Room.query.all()
    
    for room in rooms:
        available = True
        
        if fill_type in ['main', 'both']:
            conflict = MainScheduleEntry.query.filter_by(
                room_id=room.id,
                day=day,
                lesson_number=lesson,
                semester=semester
            ).first()
            
            if conflict:
                available = False
        
        if fill_type in ['current', 'both']:
            conflict = ScheduleEntry.query.filter_by(
                room_id=room.id,
                day=day,
                lesson_number=lesson,
                week_number=week,
                semester=semester
            ).first()
            
            if conflict:
                available = False
        
        if available:
            return room
    
    return None

def create_admin_user():
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', role='admin')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()

def populate_initial_data():
    from initial_data import TEACHER_INITIAL_LOAD, SUBJECTS, GROUPS, ROOMS
    
    from sqlalchemy import inspect, text
    
    # Создаем таблицу group_subject если она не существует
    inspector = inspect(db.engine)
    
    # Проверяем и создаем таблицу group_subject с нужными полями
    if 'group_subject' not in inspector.get_table_names():
        print("Создаем таблицу group_subject...")
        # Создаем таблицу вручную с дополнительными полями
        with db.engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE group_subject (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER,
                    subject_id INTEGER,
                    teacher_id INTEGER,
                    hours_per_week INTEGER DEFAULT 0,
                    total_hours_semester1 INTEGER DEFAULT 0,
                    total_hours_semester2 INTEGER DEFAULT 0,
                    FOREIGN KEY (group_id) REFERENCES "group" (id),
                    FOREIGN KEY (subject_id) REFERENCES subject (id),
                    FOREIGN KEY (teacher_id) REFERENCES teacher (id)
                )
            """))
            conn.commit()
    else:
        # Проверяем существование колонок total_hours_semester1 и total_hours_semester2
        try:
            with db.engine.connect() as conn:
                # Проверяем существование колонок
                columns = conn.execute(text("PRAGMA table_info(group_subject)")).fetchall()
                column_names = [col[1] for col in columns]
                
                if 'total_hours_semester1' not in column_names:
                    print("Добавляем колонку total_hours_semester1...")
                    conn.execute(text("ALTER TABLE group_subject ADD COLUMN total_hours_semester1 INTEGER DEFAULT 0"))
                
                if 'total_hours_semester2' not in column_names:
                    print("Добавляем колонку total_hours_semester2...")
                    conn.execute(text("ALTER TABLE group_subject ADD COLUMN total_hours_semester2 INTEGER DEFAULT 0"))
                
                conn.commit()
        except Exception as e:
            print(f"Ошибка при проверке/добавлении колонок: {e}")
    
    # Проверяем и создаем таблицу group_practice
    if 'group_practice' not in inspector.get_table_names():
        print("Создаем таблицу group_practice...")
        GroupPractice.__table__.create(db.engine)
    
    # Добавляем начальные данные
    for teacher_name in TEACHER_INITIAL_LOAD.keys():
        if not Teacher.query.filter_by(name=teacher_name).first():
            db.session.add(Teacher(name=teacher_name))
    
    for subject_name in SUBJECTS:
        if not Subject.query.filter_by(name=subject_name).first():
            db.session.add(Subject(name=subject_name))
    
    for group_name in GROUPS:
        if not Group.query.filter_by(name=group_name).first():
            course = int(group_name[0]) if group_name[0].isdigit() else 1
            db.session.add(Group(name=group_name, course=course))
    
    for room_name in ROOMS:
        if not Room.query.filter_by(name=room_name).first():
            db.session.add(Room(name=room_name))
    
    if not AppSettings.query.filter_by(key='current_week').first():
        db.session.add(AppSettings(key='current_week', value='1'))
    
    if not AppSettings.query.filter_by(key='current_semester').first():
        db.session.add(AppSettings(key='current_semester', value='1'))
    
    db.session.commit()

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5100)
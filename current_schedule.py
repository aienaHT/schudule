# current_schedule.py
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required
from models import db, ScheduleEntry, MainScheduleEntry, Group, Subject, Teacher, Room
from initial_data import AVAILABLE_DAYS, AVAILABLE_PAIRS, get_lesson_time, get_pair_number, get_lessons_in_pair, is_zero_lesson_pair

current_schedule_bp = Blueprint('current_schedule', __name__)

@current_schedule_bp.route('/current_schedule')
@login_required
def current_schedule_page():
    """Страница текущего расписания с возможностью редактирования"""
    day = request.args.get('day', 'Понедельник')
    week = request.args.get('week', '1')
    semester = request.args.get('semester', '1')
    
    # Получаем текущее расписание
    entries = ScheduleEntry.query.filter_by(
        day=day,
        week_number=int(week),
        semester=int(semester)
    ).all()
    
    # Получаем основное расписание для сравнения
    main_entries = MainScheduleEntry.query.filter_by(
        day=day,
        semester=int(semester)
    ).all()
    
    # Группируем по парам
    schedule_by_pair = {}
    all_groups = set()
    
    for entry in entries:
        pair_num = get_pair_number(entry.day, entry.lesson_number)
        if pair_num not in schedule_by_pair:
            schedule_by_pair[pair_num] = {}
        
        if entry.group.name not in schedule_by_pair[pair_num]:
            schedule_by_pair[pair_num][entry.group.name] = []
        
        schedule_by_pair[pair_num][entry.group.name].append({
            'id': entry.id,
            'subject': entry.subject.name,
            'teacher': entry.teacher.name,
            'room': entry.room.name,
            'lesson_number': entry.lesson_number,
            'time': get_lesson_time(entry.day, entry.lesson_number),
            'is_changed': entry.is_changed
        })
        
        all_groups.add(entry.group.name)
    
    # Получаем всех преподавателей, предметы, группы и комнаты для форм
    all_teachers = [t.name for t in Teacher.query.order_by(Teacher.name).all()]
    all_subjects = [s.name for s in Subject.query.order_by(Subject.name).all()]
    all_groups_list = [g.name for g in Group.query.order_by(Group.name).all()]
    all_rooms = [r.name for r in Room.query.order_by(Room.name).all()]
    
    return render_template('current_schedule.html',
                         day=day,
                         week=week,
                         semester=semester,
                         schedule_by_pair=schedule_by_pair,
                         all_groups=sorted(list(all_groups)),
                         all_teachers=all_teachers,
                         all_subjects=all_subjects,
                         all_groups_list=all_groups_list,
                         all_rooms=all_rooms,
                         available_days=AVAILABLE_DAYS,
                         available_pairs=AVAILABLE_PAIRS.get(day, []),
                         get_lessons_in_pair=get_lessons_in_pair)

@current_schedule_bp.route('/api/current/add_entry', methods=['POST'])
@login_required
def add_entry():
    """Добавить запись в текущее расписание"""
    try:
        data = request.get_json()
        
        # Проверка: для 0 урока только "Разговоры о важном"
        day = data['day']
        lesson_number = int(data['lesson_number'])
        subject = data['subject']
        
        if day in ["Понедельник", "Четверг"] and lesson_number == 0 and subject != "Разговоры о важном":
            return jsonify({'success': False, 'message': 'На 0 урок можно поставить только "Разговоры о важном"'})
        
        # Находим объекты
        group = Group.query.filter_by(name=data['group']).first()
        subject_obj = Subject.query.filter_by(name=subject).first()
        teacher = Teacher.query.filter_by(name=data['teacher']).first()
        room = Room.query.filter_by(name=data['room']).first()
        
        if not all([group, subject_obj, teacher, room]):
            return jsonify({'success': False, 'message': 'Один из объектов не найден'})
        
        # Проверка конфликтов
        conflict = ScheduleEntry.query.filter_by(
            group_id=group.id,
            day=day,
            lesson_number=lesson_number,
            week_number=int(data['week']),
            semester=int(data['semester'])
        ).first()
        
        if conflict:
            return jsonify({'success': False, 'message': 'Конфликт: группа уже занята в это время'})
        
        # Создаем запись
        entry = ScheduleEntry(
            group_id=group.id,
            subject_id=subject_obj.id,
            teacher_id=teacher.id,
            room_id=room.id,
            day=day,
            lesson_number=lesson_number,
            week_number=int(data['week']),
            semester=int(data['semester']),
            is_changed=True
        )
        
        db.session.add(entry)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Запись добавлена', 'id': entry.id})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'})

@current_schedule_bp.route('/api/current/delete_entry/<int:entry_id>', methods=['DELETE'])
@login_required
def delete_entry(entry_id):
    """Удалить запись из текущего расписания"""
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

@current_schedule_bp.route('/api/current/update_entry/<int:entry_id>', methods=['PUT'])
@login_required
def update_entry(entry_id):
    """Обновить запись в текущем расписании"""
    try:
        data = request.get_json()
        entry = ScheduleEntry.query.get(entry_id)
        
        if not entry:
            return jsonify({'success': False, 'message': 'Запись не найдена'})
        
        # Обновляем поля
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
        
        return jsonify({'success': True, 'message': 'Запись обновлена'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'})
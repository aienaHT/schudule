from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='user')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Teacher(db.Model):
    __tablename__ = 'teacher'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)


class Subject(db.Model):
    __tablename__ = 'subject'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)


class Group(db.Model):
    __tablename__ = 'group'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    course = db.Column(db.Integer, nullable=False, default=1)


class Room(db.Model):
    __tablename__ = 'room'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)


class TeacherSubject(db.Model):
    __tablename__ = 'teacher_subject'
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)


class GroupSubject(db.Model):
    __tablename__ = 'group_subject'
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=True)
    hours_per_week = db.Column(db.Integer, default=0)
    total_hours_semester1 = db.Column(db.Integer, default=0)
    total_hours_semester2 = db.Column(db.Integer, default=0)

    # Добавляем связи
    group = db.relationship('Group', backref='group_subjects')
    subject = db.relationship('Subject', backref='group_subjects')
    teacher = db.relationship('Teacher', backref='group_subjects')


class AppSettings(db.Model):
    __tablename__ = 'app_settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), nullable=False, unique=True)
    value = db.Column(db.String(200), nullable=False)


class ScheduleEntry(db.Model):
    __tablename__ = 'schedule_entry'
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    day = db.Column(db.String(20), nullable=False)
    lesson_number = db.Column(db.Integer, nullable=False)
    week_number = db.Column(db.Integer, nullable=False)
    week_parity = db.Column(db.String(10), default='both')
    semester = db.Column(db.Integer, nullable=False)
    is_changed = db.Column(db.Boolean, default=False)
    is_combined = db.Column(db.Boolean, default=False)

    # Добавляем связи
    group = db.relationship('Group', backref='schedule_entries')
    subject = db.relationship('Subject', backref='schedule_entries')
    teacher = db.relationship('Teacher', backref='schedule_entries')
    room = db.relationship('Room', backref='schedule_entries')


class MainScheduleEntry(db.Model):
    __tablename__ = 'main_schedule_entry'
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    day = db.Column(db.String(20), nullable=False)
    lesson_number = db.Column(db.Integer, nullable=False)
    week_parity = db.Column(db.String(10), default='both')
    semester = db.Column(db.Integer, nullable=False)
    is_combined = db.Column(db.Boolean, default=False)

    # Добавляем связи
    group = db.relationship('Group', backref='main_schedule_entries')
    subject = db.relationship('Subject', backref='main_schedule_entries')
    teacher = db.relationship('Teacher', backref='main_schedule_entries')
    room = db.relationship('Room', backref='main_schedule_entries')


class AutoFillLog(db.Model):
    __tablename__ = 'auto_fill_log'
    id = db.Column(db.Integer, primary_key=True)
    week_number = db.Column(db.Integer, nullable=False)
    semester = db.Column(db.Integer, nullable=False)
    fill_type = db.Column(db.String(20), nullable=False)
    entries_added = db.Column(db.Integer, default=0)
    conflicts = db.Column(db.Integer, default=0)
    errors = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())


class GroupPractice(db.Model):
    __tablename__ = 'group_practice'
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False, unique=True)
    day = db.Column(db.String(20), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=True)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=True)

    # Добавляем связи
    group = db.relationship('Group', backref='practice')
    subject = db.relationship('Subject', backref='practices')
    teacher = db.relationship('Teacher', backref='practices')
    room = db.relationship('Room', backref='practices')
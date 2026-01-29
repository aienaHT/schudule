from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), default='viewer')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Teacher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    
    def __repr__(self):
        return f'<Teacher {self.name}>'

class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    
    def __repr__(self):
        return f'<Subject {self.name}>'

class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    course = db.Column(db.Integer, nullable=False)
    
    def __repr__(self):
        return f'<Group {self.name}>'

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    
    def __repr__(self):
        return f'<Room {self.name}>'

class TeacherSubject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    
    teacher = db.relationship('Teacher', backref=db.backref('subjects', lazy=True))
    subject = db.relationship('Subject', backref=db.backref('teachers', lazy=True))

class GroupSubject(db.Model):
    __tablename__ = 'group_subject'
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=True)
    hours_per_week = db.Column(db.Integer, default=0)
    total_hours_semester1 = db.Column(db.Integer, default=0)  # ДОБАВЛЕНО
    total_hours_semester2 = db.Column(db.Integer, default=0)  # ДОБАВЛЕНО
    
    group = db.relationship('Group', backref=db.backref('group_subjects', lazy=True))
    subject = db.relationship('Subject', backref=db.backref('group_subjects', lazy=True))
    teacher = db.relationship('Teacher', backref=db.backref('group_assignments', lazy=True))

class GroupPractice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    day = db.Column(db.String(20), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=True)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=True)
    
    group = db.relationship('Group', backref=db.backref('practice', lazy=True))
    subject = db.relationship('Subject', backref=db.backref('practices', lazy=True))
    teacher = db.relationship('Teacher', backref=db.backref('practices', lazy=True))
    room = db.relationship('Room', backref=db.backref('practices', lazy=True))

class ScheduleEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    day = db.Column(db.String(20), nullable=False)
    lesson_number = db.Column(db.Integer, nullable=False)
    week_number = db.Column(db.Integer, default=1)
    week_parity = db.Column(db.String(10), default='both')
    semester = db.Column(db.Integer, default=1)
    is_changed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    group = db.relationship('Group', backref=db.backref('schedule_entries', lazy=True))
    subject = db.relationship('Subject', backref=db.backref('schedule_entries', lazy=True))
    teacher = db.relationship('Teacher', backref=db.backref('schedule_entries', lazy=True))
    room = db.relationship('Room', backref=db.backref('schedule_entries', lazy=True))

class MainScheduleEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    day = db.Column(db.String(20), nullable=False)
    lesson_number = db.Column(db.Integer, nullable=False)
    week_parity = db.Column(db.String(10), default='both')
    semester = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    group = db.relationship('Group', backref=db.backref('main_schedule_entries', lazy=True))
    subject = db.relationship('Subject', backref=db.backref('main_schedule_entries', lazy=True))
    teacher = db.relationship('Teacher', backref=db.backref('main_schedule_entries', lazy=True))
    room = db.relationship('Room', backref=db.backref('main_schedule_entries', lazy=True))

class AutoFillLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    week_number = db.Column(db.Integer, nullable=False)
    semester = db.Column(db.Integer, nullable=False)
    fill_type = db.Column(db.String(20), nullable=False)
    entries_added = db.Column(db.Integer, default=0)
    conflicts = db.Column(db.Integer, default=0)
    errors = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AppSettings(db.Model):
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(100), nullable=False)
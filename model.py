import enum
from datetime import datetime
from enum import Enum

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship

from app import db


class Role(enum.Enum):
    STUDENT = 'STUDENT'
    STAFF = 'STAFF'


class User(db.Model):
    __abstract__ = True

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def role(self):
        return


class Student(User):
    __tablename__ = "student"
    __table_args__ = {"extend_existing": True}

    identifier = db.Column(db.String(50), unique=True, nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=False)

    @property
    def role(self):
        return Role.STUDENT


class Staff(User):
    __tablename__ = 'staff'
    __table_args__ = {"extend_existing": True}

    @property
    def role(self):
        return Role.STAFF


class Course(db.Model):
    __tablename__ = "course"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    # associated entities
    creator_id = db.Column(db.Integer, db.ForeignKey("staff.id"), nullable=False)
    creator = relationship(
        Staff,
        backref="courses",
        primaryjoin="Course.creator_id == Staff.id",
    )

    def __init__(self, name):
        self.name = name

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name
        }


class Environment(db.Model):
    __tablename__ = "environment"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    docker_image = db.Column(db.String(255), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, name, docker_image):
        self.name = name
        self.docker_image = docker_image

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'docker_image': self.docker_image,
        }


class Exam(db.Model):
    __tablename__ = 'exam'

    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False)  # INACTIVE, ACTIVE, COMPLETED
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    # associated entities
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    course = relationship(
        Course,
        backref="exams",
        primaryjoin="Exam.course_id == Course.id",
    )

    def __init__(self, description, status, course_id):
        self.description = description
        self.status = status
        self.course_id = course_id

    def to_dict(self):
        return {
            'id': self.id,
            'description': self.description,
            'status': self.status
        }


class ExamCompletion(db.Model):
    __tablename__ = 'exam_completion'

    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'), primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), primary_key=True)
    completed = db.Column(db.Boolean, nullable=False, default=False)
    completion_reason = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, exam_id, student_id, completed=False, completion_reason=None):
        self.exam_id = exam_id
        self.student_id = student_id
        self.completed = completed
        self.completion_reason = completion_reason

    def to_dict(self):
        return {
            'completed': self.completed,

        }


class Assignment(db.Model):
    __tablename__ = "assignment"
    __table_args__ = (UniqueConstraint('index', 'exam_id', name='_exam_assignment_index_uc'),)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(512), nullable=False)
    index = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    # associated entities
    exam_id = db.Column(db.Integer, db.ForeignKey("exam.id"), nullable=False)
    exam = relationship(
        Exam,
        backref="assignments",
        primaryjoin="Assignment.exam_id == Exam.id",
    )

    def __init__(self, index, name, text):
        self.index = index
        self.name = name
        self.text = text


class ExamViolation(db.Model):
    __tablename__ = 'exam_violation'

    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'))
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    assignment_id = db.Column(db.String)
    violation_type = db.Column(db.String, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, exam_id, student_id, assignment_id, violation_type):
        self.exam_id = exam_id
        self.student_id = student_id
        self.assignment_id = assignment_id
        self.violation_type = violation_type

    def to_dict(self):
        return {
            'exam_id': self.exam_id,
            'student_id': self.student_id,
            'assignment_id': self.assignment_id
        }


class ViolationType(Enum):
    COPY_PASTE_VIOLATION = 'COPY_PASTE_VIOLATION'
    TAB_VIOLATION = 'TAB_VIOLATION'

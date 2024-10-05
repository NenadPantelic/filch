import json

from app import session
from dao.course_dao import CourseDAO
from dao.environment_dao import EnvironmentDAO
from dao.exam_dao import ExamDAO
from dao.staff_dao import StaffDAO
from dao.student_dao import StudentDAO
from model import Environment, Student, Staff, Course, Exam
from util.password_util import hash_password


def load_json(filepath):
    with open(filepath, 'r') as fp:
        return json.load(fp)


environment_dao = EnvironmentDAO(session)
student_dao = StudentDAO(session)
staff_dao = StaffDAO(session)
course_dao = CourseDAO(session)
exam_dao = ExamDAO(session)

# environments
ENVIRONMENTS = load_json('resources/environments.json')
for environment in ENVIRONMENTS:
    environment_dao.insert(Environment(**environment))

# # students
STUDENTS = load_json('resources/students.json')
for student in STUDENTS:
    student['password'] = hash_password(student['password'])
    student['active'] = True
    student_dao.insert(Student(**student))

# staff
STAFF = load_json('resources/staff.json')
for staff in STAFF:
    staff['password'] = hash_password(staff['password'])
    staff_dao.insert(Staff(**staff))

# courses
COURSES = load_json('resources/courses.json')
staff = staff_dao.find_by_id(1)

for course_data in COURSES:
    course = Course(**course_data)
    course.creator = staff
    course_dao.insert(course)

# exams
EXAMS = load_json('resources/exams.json')
for exam_data in EXAMS:
    course = course_dao.find_by_name(exam_data["course_name"])
    exam_data.pop("course_name")
    exam_data["course_id"] = course.id
    exam = Exam(**exam_data)

    exam_dao.insert(exam)

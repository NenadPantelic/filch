from dao.generic_dao import GenericDAO
from model import Exam


class ExamDAO(GenericDAO):
    def __init__(self, session):
        super().__init__(session, Exam)

    def find_by_course_id(self, course_id):
        return Exam.query.filter_by(course_id=course_id).all()

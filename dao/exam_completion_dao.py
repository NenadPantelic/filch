from sqlalchemy import and_

from dao.generic_dao import GenericDAO
from model import ExamCompletion


class ExamCompletionDAO(GenericDAO):
    def __init__(self, session):
        super().__init__(session, ExamCompletion)

    def find_by_exam_and_student(self, exam_id, student_id):
        return ExamCompletion.query.filter_by(exam_id=exam_id, student_id=student_id).first()

    def find_completed_by_exams_and_student(self, exam_ids, student_id):
        return ExamCompletion.query.filter(
            and_(ExamCompletion.exam_id.in_(exam_ids), ExamCompletion.student_id == student_id,
                 ExamCompletion.completed == True)).all()

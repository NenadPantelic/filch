from dao.generic_dao import GenericDAO
from model import Course


class CourseDAO(GenericDAO):
    def __init__(self, session):
        super().__init__(session, Course)

    def find_by_name(self, name):
        return Course.query.filter_by(name=name).first()

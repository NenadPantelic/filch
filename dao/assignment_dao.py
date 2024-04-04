from dao.generic_dao import GenericDAO
from model import Assignment


class AssignmentDAO(GenericDAO):
    def __init__(self, session):
        super().__init__(session, Assignment)

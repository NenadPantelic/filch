from dao.generic_dao import GenericDAO
from model import Environment


class EnvironmentDAO(GenericDAO):
    def __init__(self, session):
        super().__init__(session, Environment)

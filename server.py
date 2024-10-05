from functools import wraps

from flask import jsonify, request, g

from app import db, app, session, violations_limit_per_exam
from auth import AuthManager, UserContext
from dao.assignment_dao import AssignmentDAO
from dao.course_dao import CourseDAO
from dao.environment_dao import EnvironmentDAO
from dao.exam_completion_dao import ExamCompletionDAO
from dao.exam_dao import ExamDAO
from dao.exam_violation_dao import ExamViolationDAO
from dao.staff_dao import StaffDAO
from dao.student_dao import StudentDAO
from exception import HogwartsException, UNAUTHORIZED
from minerva_client import MinervaClient
from model import Exam, ExamCompletion, Role, ExamViolation
from util.logging import logger
from util.password_util import password_matches

auth_manager = AuthManager(180)

BEARER = 'Bearer '

WHITELISTED_URLS = ['/api/v1/auth']

environment_dao = EnvironmentDAO(session)
student_dao = StudentDAO(session)
staff_dao = StaffDAO(session)
course_dao = CourseDAO(session)
exam_dao = ExamDAO(session)
exam_completion_dao = ExamCompletionDAO(session)
exam_violation_dao = ExamViolationDAO(session)
assignment_dao = AssignmentDAO(session)

minerva_client = MinervaClient('http://localhost:9091', 'X-albus-user-id', 3)


#### Authn/z
# Authentication endpoint
@app.route('/api/v1/auth', methods=['POST'])
def login():
    data = request.get_json() or {}
    identifier = data.get('identifier')
    password = data.get('password')

    if not identifier or not password:
        return bad_request('Bad credentials.')

    user = student_dao.find_active_by_identifier(identifier)
    if not user:
        user = staff_dao.find_by_identifier(identifier)

    if not user or not password_matches(password, user.password):
        return unauthorized('Bad credentials')

    access_token = auth_manager.create_token(user)
    g.token = access_token
    return {'access_token': access_token, 'role': user.role.value}, 200


# Authorization decorator for any authenticated user
def auth_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            identity = get_identity()
        except Exception as e:
            raise UNAUTHORIZED
        return fn(*args, **kwargs)

    return wrapper


# Authorization decorator for staff
def staff_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        current_user = get_identity()
        if current_user.role != Role.STAFF:
            return forbidden('Staff access required')
        return fn(*args, **kwargs)

    return wrapper


# Authorization decorator for students
def student_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        current_user = get_identity()
        if current_user.role != Role.STUDENT:
            return forbidden('Student access required')
        return fn(*args, **kwargs)

    return wrapper


@app.before_request
def set_auth_token():
    target_url = request.url
    for url in WHITELISTED_URLS:
        if target_url.endswith(url):
            return

    authz_header = request.headers.get('Authorization')
    token = None
    if authz_header and authz_header.startswith('Bearer '):
        token = authz_header[len(BEARER):]
    g.token = token


def get_identity() -> UserContext:
    return auth_manager.get_user(g.token)


# -----------------
# ENVIRONMENTS #
@app.route('/api/v1/environments', methods=['GET'])
@auth_required
def list_environments():
    logger.info("Received a request to list all environments")
    return to_list_response("environments", environment_dao.find_all()), 200


# --------------------
# COURSES
@app.route('/api/v1/courses', methods=['GET'])
@auth_required
def list_courses():
    logger.info("Received a request to list all courses")
    return to_list_response("courses", course_dao.find_all()), 200


# # --------------------
# EXAMS
@app.route('/api/v1/courses/<int:course_id>/exams', methods=['GET'])
@auth_required
def list_exams(course_id):
    # the only check atm, just check if the course exists since all exams will be under that course
    course = course_dao.find_by_id(course_id)
    if not course:
        return not_found("Course not found.")

    user = get_identity()
    exams = exam_dao.find_by_course_id(course_id)

    if user.role == Role.STAFF:
        return to_list_response('exams', exam_dao.find_by_course_id(course_id)), 200

    # TODO: improve this, dummy brute-force
    exam_ids = [exam.id for exam in exams]
    completed_exams_ids = set([ec.exam_id for ec in
                               exam_completion_dao.find_completed_by_exams_and_student(exam_ids, user.id)])

    exam_representations = []
    for exam in exams:
        exam_representation = exam.to_dict()
        if exam.id in completed_exams_ids:
            exam_representation['status'] = 'COMPLETED'
        exam_representations.append(exam_representation)

    return {'data': exam_representations}, 200


@app.route('/api/v1/exams/<int:exam_id>', methods=['GET'])
@auth_required
def get_exam(exam_id):
    exam = exam_dao.find_by_id(exam_id)
    if not exam:
        return not_found('Exam not found')

    # Check if the exam is active
    if exam.status != 'ACTIVE':
        return conflict('Exam is not active')

    current_user = get_identity()
    if current_user.role != Role.STAFF:
        student_id = current_user.id
        # Check if the student has started or completed the exam
        exam_completion = exam_completion_dao.find_by_exam_and_student(exam_id=exam_id, student_id=student_id)
        if not exam_completion or exam_completion.status == 'COMPLETED':
            return conflict('Exam not active, no permission to access.')

    return exam.to_dict(), 200


@app.route('/api/v1/staff/exams/<int:exam_id>/start', methods=['POST'])
@staff_required
def start_exam(exam_id):
    exam = exam_dao.find_by_id(exam_id)
    if not exam:
        return not_found('Exam not found')

    # Check if the exam is active
    if exam.status != 'INACTIVE':
        return conflict('Exam is already active or completed')

    exam.status = 'ACTIVE'
    exam_dao.session_commit()
    return exam.to_dict(), 200


# Endpoint for completing an exam
@app.route('/api/v1/staff/exams/<int:exam_id>/complete', methods=['POST'])
@student_required
def complete_exam(exam_id):
    exam = exam_dao.find_by_id(exam_id)
    if not exam:
        return not_found('Exam not found')

    # Check if the exam is active
    if exam.status != 'ACTIVE':
        return forbidden('Exam is not active')

    exam.status = 'COMPLETE'
    exam_dao.session_commit()
    return exam.to_dict(), 200


# # --------------------
# STUDENT EXAMS
@app.route('/api/v1/exams/<int:exam_id>/start', methods=['POST'])
@student_required
def start_exam_as_student(exam_id):
    exam = exam_dao.find_by_id(exam_id)
    if not exam:
        return not_found('Exam not found')

    # Check if the exam is active
    if exam.status != 'ACTIVE':
        return conflict('Exam is not active')

    student_id = get_identity().id
    exam_completion = exam_completion_dao.find_by_exam_and_student(exam_id=exam_id, student_id=student_id)
    if exam_completion:
        return conflict('Exam already started')

    exam_completion_dao.insert(ExamCompletion(exam_id, student_id))

    return exam.to_dict(), 200


# Endpoint for completing an exam
@app.route('/api/v1/exams/<int:exam_id>/complete', methods=['POST'])
@student_required
def complete_exam_as_student(exam_id):
    exam = exam_dao.find_by_id(exam_id)
    if not exam:
        return not_found('Exam not found')

    # Check if the exam is active
    if exam.status != 'ACTIVE':
        return forbidden('Exam is not active')

    student_id = get_identity().id
    exam_completion = exam_completion_dao.find_by_exam_and_student(exam_id=exam_id, student_id=student_id)
    if not exam_completion:
        return bad_request('Exam not started by the student')

    if exam_completion.completed:
        return conflict('Exam already completed')

    exam_completion.completed = True
    exam_completion_dao.session_commit()

    return exam.to_dict(), 200


# Endpoint for completing an exam
@app.route('/api/v1/exams/<int:exam_id>/violation', methods=['POST'])
@student_required
def report_exam_violation(exam_id):
    exam = Exam.query.get(exam_id)
    if not exam:
        return not_found('Exam not found')

    data = request.get_json() or {}

    assignment_id = data.get('assignment_id')
    violation_type = data.get('violation_type')

    student_id = get_identity().id

    exam_violation = exam_violation_dao.insert(
        ExamViolation(exam_id, student_id, assignment_id, violation_type)
    )

    num_of_exam_violations = exam_violation_dao.count_exam_violations(student_id, assignment_id)
    # if violations limit reached, complete the exam for this user
    if num_of_exam_violations >= violations_limit_per_exam:
        exam_completion_dao.insert(
            ExamCompletion(exam_id, student_id, True, "Course policy violated")
        )

    return exam_violation.to_dict(), 200


# --------------------
# ASSIGNMENTS
@app.route('/api/v1/exams/<int:exam_id>/assignments/<int:assignment_id>', methods=['GET'])
@auth_required
def get_assignment(exam_id, assignment_id):
    check_exam_access(exam_id)

    assignment = assignment_dao.find_by_id(assignment_id)
    if assignment.exam_id != exam_id:
        return forbidden('Assignment is not associated to target exam.')

    return assignment.to_dict(), 200


# --------------------
# SUBMISSIONS
@app.route('/api/v1/exams/<int:exam_id>/assignments/<int:assignment_id>/submit', methods=['GET'])
@auth_required
def submit(exam_id, assignment_id):
    data = request.get_json() or {}
    environment = data.get('environment')
    content = data.get('content')

    if not environment or not content:
        return bad_request('Code submission is invalid.')

    check_exam_access(exam_id)

    assignment = assignment_dao.find_by_id(assignment_id)
    if not assignment:
        return not_found("Assignment not found.")

    if assignment.exam_id != exam_id:
        return forbidden('Assignment is not associated to target exam.')

    return {
               'data': minerva_client.submit(assignment_id, assignment.name, environment, exam_id, content,
                                             get_identity().id)
           }, 202


@app.route('/api/v1/exams/<int:exam_id>/submissions', methods=['GET'])
@auth_required
def list_submissions(exam_id):
    check_exam_access_by_id(exam_id)
    return {'data': minerva_client.list_my_submissions(exam_id, 0, 50, get_identity().id)}, 200


@app.route('/api/v1/exams/<int:exam_id>/results', methods=['GET'])
@auth_required
def get_exam_results(exam_id):
    check_exam_access_by_id(exam_id)
    return {'data': minerva_client.list_my_submissions(exam_id, 0, 50, get_identity().id)}, 200


@app.route('/api/v1/submissions', methods=['GET'])
@staff_required
def list_all_submissions():
    return {'data': minerva_client.list_all_submissions(0, 50, get_identity().id)}, 200


@app.route('/api/v1/exams/<int:exam_id>/submissions/<int:submission_id>', methods=['GET'])
@auth_required
def get_submission(exam_id, submission_id):
    check_exam_access_by_id(exam_id)
    return {'data': minerva_client.get_submission(submission_id, get_identity().id)}, 200


@app.route('/api/v1/assignments/<int:assignment_id>/allowance', methods=['GET'])
@auth_required
def get_submission_allowance(assignment_id):
    assignment = assignment_dao.find_by_id(assignment_id)
    if not assignment:
        return not_found("Assignment not found.")

    check_exam_access(assignment.exam)
    return {'data': minerva_client.get_allowance(assignment_id, get_identity().id)}, 200


def check_exam_access_by_id(exam_id):
    exam = Exam.query.get(exam_id)
    if not exam:
        return not_found('Exam not found')
    return check_exam_access(exam)


def check_exam_access(exam):
    # Check if the exam is active
    if exam.status != 'ACTIVE':
        return forbidden('Exam is not active')

    current_user = get_identity()
    if current_user.role != Role.STAFF:
        student_id = current_user.id
        # Check if the student has started or completed the exam
        exam_completion = exam_completion_dao.find_by_exam_and_student(exam_id=exam.id, student_id=student_id)
        if not exam_completion or exam_completion.completed:
            return forbidden('Exam not active, no permission to access.')


def to_list_response(resource, collection):
    return {
        "data": {
            resource: [
                item.to_dict() for item in collection
            ]
        }
    }


def to_response(entity):
    return {
        "data": entity.to_dict()
    }


@app.errorhandler(Exception)
def handle_error(error):
    logger.error(f'An error occurred: {error}')
    if isinstance(error, HogwartsException):
        return {'error': error.message}, error.status

    return {'error': 'Internal Server Error'}, 500


def bad_request(message):
    return error_response(message, 400)


def unauthorized(message='Unauthorized'):
    return error_response(message, 401)


def forbidden(message):
    return error_response(message, 403)


def not_found(message):
    return error_response(message, 404)


def conflict(message):
    return error_response(message, 409)


def error_response(message, status_code):
    return jsonify({'error': message}), status_code


if __name__ == "__main__":
    with app.app_context() as context:
        db.create_all()
    app.run()

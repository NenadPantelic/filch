import secrets

import bcrypt

PASSWORD_LENGTH = 10


def hash_password(password: str) -> str:
    return bcrypt.hashpw(bytes(password, encoding='utf-8'), bcrypt.gensalt()).decode('utf-8')


def generate_password(hashed=True) -> str:
    plain_password = secrets.token_urlsafe(PASSWORD_LENGTH)
    return hash_password(plain_password) if hashed else plain_password


def password_matches(plain: str, hashed: str):
    return bcrypt.checkpw(_to_bytes(plain), _to_bytes(hashed))


def _to_bytes(password: str):
    return password.encode('utf-8')

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError


_password_hasher = PasswordHasher()
_dummy_password_hash = _password_hasher.hash("timing-only-password")


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerifyMismatchError):
        return False


def dummy_password_hash() -> str:
    return _dummy_password_hash

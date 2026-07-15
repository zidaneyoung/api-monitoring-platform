from argon2 import PasswordHasher


_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)

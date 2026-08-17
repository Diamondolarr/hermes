from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _get_fernet() -> Fernet:
    if not settings.encryption_key:
        raise ValueError("ENCRYPTION_KEY is not set.")
    key = settings.encryption_key.encode("utf-8")
    return Fernet(key)


def encrypt_value(value: str) -> str:
    fernet = _get_fernet()
    token = fernet.encrypt(value.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_value(value: str) -> str:
    fernet = _get_fernet()
    decrypted = fernet.decrypt(value.encode("utf-8"))
    return decrypted.decode("utf-8")


__all__ = ["encrypt_value", "decrypt_value", "InvalidToken"]

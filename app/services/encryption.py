"""Fernet encryption for platform tokens stored at rest.

Generate a key once:  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
Set it as ENCRYPTION_KEY in .env.
"""
from __future__ import annotations
from functools import lru_cache
from cryptography.fernet import Fernet, InvalidToken


@lru_cache
def _get_fernet() -> Fernet | None:
    from app.config import get_settings
    key = get_settings().encryption_key
    if not key:
        return None
    return Fernet(key.encode())


def encrypt_token(plaintext: str | None) -> str | None:
    if plaintext is None:
        return None
    f = _get_fernet()
    if f is None:
        return plaintext
    return f.encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str | None) -> str | None:
    if ciphertext is None:
        return None
    f = _get_fernet()
    if f is None:
        return ciphertext
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        return ciphertext

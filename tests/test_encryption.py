"""Tests for token encryption/decryption."""
from unittest.mock import patch
from cryptography.fernet import Fernet

from app.services.encryption import encrypt_token, decrypt_token, _get_fernet


def test_roundtrip_with_key():
    key = Fernet.generate_key().decode()
    with patch("app.services.encryption._get_fernet") as mock:
        mock.return_value = Fernet(key.encode())
        encrypted = encrypt_token("secret_token_123")
        assert encrypted != "secret_token_123"
        assert decrypt_token(encrypted) == "secret_token_123"


def test_none_passthrough():
    assert encrypt_token(None) is None
    assert decrypt_token(None) is None


def test_no_key_passthrough():
    with patch("app.services.encryption._get_fernet", return_value=None):
        assert encrypt_token("plaintext") == "plaintext"
        assert decrypt_token("plaintext") == "plaintext"


def test_decrypt_unencrypted_graceful():
    key = Fernet.generate_key().decode()
    with patch("app.services.encryption._get_fernet") as mock:
        mock.return_value = Fernet(key.encode())
        result = decrypt_token("not_a_fernet_token")
        assert result == "not_a_fernet_token"

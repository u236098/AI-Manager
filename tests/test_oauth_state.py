"""Tests for OAuth state generation and validation."""
from __future__ import annotations
import time
from unittest.mock import patch
from app.services.oauth_state import generate_state, validate_state


def test_generate_and_validate():
    state = generate_state()
    assert validate_state(state) is True


def test_tampered_state_rejected():
    state = generate_state()
    parts = state.split(".")
    tampered = parts[0] + ".aaaaaaaaaaaaaaaa"
    assert validate_state(tampered) is False


def test_malformed_state_rejected():
    assert validate_state("nope") is False
    assert validate_state("") is False
    assert validate_state("abc.def") is False


def test_expired_state_rejected():
    state = generate_state()
    with patch("app.services.oauth_state.time") as mock_time:
        mock_time.time.return_value = time.time() + 700
        assert validate_state(state) is False

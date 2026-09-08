from datetime import timedelta

import pytest

from app.core import security
from app.core.security import (
    InvalidTokenError,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    hashed = hash_password("correct-horse-battery-staple")
    assert hashed != "correct-horse-battery-staple"
    assert verify_password("correct-horse-battery-staple", hashed)
    assert not verify_password("wrong-password", hashed)


def test_access_token_roundtrip():
    token = create_access_token(user_id="user-123", role="agent")
    payload = decode_token(token, TokenType.ACCESS)

    assert payload["sub"] == "user-123"
    assert payload["role"] == "agent"
    assert payload["type"] == "access"


def test_refresh_token_rejected_as_access_token():
    token = create_refresh_token(user_id="user-123", role="customer")

    with pytest.raises(InvalidTokenError):
        decode_token(token, TokenType.ACCESS)


def test_tampered_token_rejected():
    token = create_access_token(user_id="user-123", role="customer")
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")

    with pytest.raises(InvalidTokenError):
        decode_token(tampered, TokenType.ACCESS)


def test_expired_token_rejected(monkeypatch):
    original_create = security._create_token

    def create_already_expired(subject, role, token_type, expires_delta):
        return original_create(subject, role, token_type, timedelta(seconds=-1))

    monkeypatch.setattr(security, "_create_token", create_already_expired)
    token = create_access_token(user_id="user-123", role="customer")

    with pytest.raises(InvalidTokenError):
        decode_token(token, TokenType.ACCESS)

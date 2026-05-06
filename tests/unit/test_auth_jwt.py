from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.shared.jwt import JwtError, decode_hs256, encode_hs256


def test_hs256_jwt_round_trips_with_issuer_audience_and_type() -> None:
    token = encode_hs256(
        {
            "sub": "user_1",
            "jti": "access_1",
            "token_type": "access",
            "iss": "little-bear-rag",
            "aud": "little-bear-internal",
            "exp": int((datetime.now(UTC) + timedelta(minutes=5)).timestamp()),
        },
        "secret",
    )

    claims = decode_hs256(
        token,
        "secret",
        issuer="little-bear-rag",
        audience="little-bear-internal",
        token_type="access",
    )

    assert claims["sub"] == "user_1"
    assert claims["jti"] == "access_1"


def test_hs256_jwt_rejects_invalid_signature() -> None:
    token = encode_hs256(
        {
            "sub": "user_1",
            "jti": "access_1",
            "token_type": "access",
            "exp": int((datetime.now(UTC) + timedelta(minutes=5)).timestamp()),
        },
        "secret",
    )

    with pytest.raises(JwtError) as exc_info:
        decode_hs256(token, "other-secret")

    assert exc_info.value.error_code == "JWT_SIGNATURE_INVALID"


def test_hs256_jwt_rejects_expired_token() -> None:
    token = encode_hs256(
        {
            "sub": "user_1",
            "jti": "access_1",
            "token_type": "access",
            "exp": int((datetime.now(UTC) - timedelta(minutes=1)).timestamp()),
        },
        "secret",
    )

    with pytest.raises(JwtError) as exc_info:
        decode_hs256(token, "secret")

    assert exc_info.value.error_code == "JWT_EXPIRED"

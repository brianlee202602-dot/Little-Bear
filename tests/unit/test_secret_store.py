from __future__ import annotations

import hashlib

import pytest
from app.modules.secrets.service import (
    SecretStoreError,
    decrypt_secret_value,
    encrypt_secret_value,
    validate_secret_ref,
)

MASTER_KEY = "test-master-key-" + "x" * 64


def test_secret_crypto_round_trips_without_plain_hash() -> None:
    encrypted = encrypt_secret_value(
        "secret://rag/minio/access-key",
        "minioadmin",
        MASTER_KEY,
    )

    decrypted = decrypt_secret_value(
        secret_ref="secret://rag/minio/access-key",
        ciphertext=encrypted.ciphertext,
        encryption_meta=encrypted.encryption_meta,
        master_key=MASTER_KEY,
    )

    assert decrypted == "minioadmin"
    assert encrypted.value_hash != hashlib.sha256(b"minioadmin").hexdigest()
    assert encrypted.encryption_meta["algorithm"] == "AES-256-GCM"


def test_secret_crypto_binds_ciphertext_to_secret_ref() -> None:
    encrypted = encrypt_secret_value(
        "secret://rag/minio/access-key",
        "minioadmin",
        MASTER_KEY,
    )

    with pytest.raises(SecretStoreError, match="cannot be decrypted"):
        decrypt_secret_value(
            secret_ref="secret://rag/minio/secret-key",
            ciphertext=encrypted.ciphertext,
            encryption_meta=encrypted.encryption_meta,
            master_key=MASTER_KEY,
        )


def test_secret_ref_validation_requires_rag_namespace() -> None:
    validate_secret_ref("secret://rag/auth/jwt-signing-key")

    with pytest.raises(SecretStoreError, match="secret://rag/"):
        validate_secret_ref("secret://other/auth/jwt-signing-key")

    with pytest.raises(SecretStoreError, match="must match"):
        validate_secret_ref("secret://rag/too-shallow")

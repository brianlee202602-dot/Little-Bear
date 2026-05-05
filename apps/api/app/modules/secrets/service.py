from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from secrets import token_bytes
from typing import Any

from app.shared.settings import get_settings
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy import text
from sqlalchemy.orm import Session

SECRET_REF_PATTERN = re.compile(
    r"^secret://(?P<namespace>[a-z0-9_-]+)/(?P<service>[A-Za-z0-9._-]+)/(?P<name>[A-Za-z0-9._/-]+)$"
)
SECRET_REF_PREFIX = "secret://rag/"
ENCRYPTION_ALGORITHM = "AES-256-GCM"
KDF_ALGORITHM = "HKDF-SHA256"
KEY_ID = "local-v1"
HKDF_INFO = b"little-bear-secret-store-v1"
HASH_CONTEXT = b"little-bear-secret-store-value-hash-v1"


class SecretStoreError(Exception):
    """Secret Store operation failed."""


@dataclass(frozen=True)
class EncryptedSecret:
    ciphertext: bytes
    encryption_meta: dict[str, str]
    value_hash: str


@dataclass(frozen=True)
class SecretWriteResult:
    secret_ref: str
    action: str
    status: str
    value_hash: str


@dataclass(frozen=True)
class SecretListItem:
    secret_ref: str
    scope_type: str
    scope_id: str
    status: str
    value_hash: str
    created_at: datetime | None
    updated_at: datetime | None
    rotated_at: datetime | None


@dataclass(frozen=True)
class SecretVerifyResult:
    secret_ref: str
    status: str
    readable: bool
    value_hash: str


class SecretStoreService:
    """PostgreSQL-backed encrypted Secret Store."""

    def put_secret(
        self,
        session: Session,
        *,
        secret_ref: str,
        secret_value: str,
        scope_type: str = "global",
        scope_id: str = "global",
    ) -> SecretWriteResult:
        validate_secret_ref(secret_ref)
        if secret_value == "":
            raise SecretStoreError("secret value cannot be empty")

        master_key = get_required_master_key()
        encrypted = encrypt_secret_value(secret_ref, secret_value, master_key)
        existing_id = session.execute(
            text("SELECT id::text AS id FROM secrets WHERE secret_ref = :secret_ref FOR UPDATE"),
            {"secret_ref": secret_ref},
        ).scalar_one_or_none()

        params = {
            "secret_ref": secret_ref,
            "ciphertext": encrypted.ciphertext,
            "encryption_meta_json": json.dumps(
                encrypted.encryption_meta,
                separators=(",", ":"),
                sort_keys=True,
            ),
            "value_hash": encrypted.value_hash,
            "scope_type": scope_type,
            "scope_id": scope_id,
        }
        if existing_id is None:
            session.execute(
                text(
                    """
                    INSERT INTO secrets(
                        id, scope_type, scope_id, secret_ref, ciphertext,
                        encryption_meta_json, value_hash, status
                    )
                    VALUES (
                        :id, :scope_type, :scope_id, :secret_ref, :ciphertext,
                        CAST(:encryption_meta_json AS jsonb), :value_hash, 'active'
                    )
                    """
                ),
                {"id": str(uuid.uuid4()), **params},
            )
            action = "created"
        else:
            session.execute(
                text(
                    """
                    UPDATE secrets
                    SET
                        scope_type = :scope_type,
                        scope_id = :scope_id,
                        ciphertext = :ciphertext,
                        encryption_meta_json = CAST(:encryption_meta_json AS jsonb),
                        value_hash = :value_hash,
                        status = 'active',
                        updated_at = now(),
                        rotated_at = now()
                    WHERE secret_ref = :secret_ref
                    """
                ),
                params,
            )
            action = "updated"

        return SecretWriteResult(
            secret_ref=secret_ref,
            action=action,
            status="active",
            value_hash=encrypted.value_hash,
        )

    def list_secrets(
        self,
        session: Session,
        *,
        include_deleted: bool = False,
    ) -> list[SecretListItem]:
        rows = session.execute(
            text(
                """
                SELECT
                    secret_ref,
                    scope_type,
                    scope_id,
                    status,
                    value_hash,
                    created_at,
                    updated_at,
                    rotated_at
                FROM secrets
                WHERE (:include_deleted = true OR status <> 'deleted')
                ORDER BY secret_ref
                """
            ),
            {"include_deleted": include_deleted},
        ).all()
        return [
            SecretListItem(
                secret_ref=row._mapping["secret_ref"],
                scope_type=row._mapping["scope_type"],
                scope_id=row._mapping["scope_id"],
                status=row._mapping["status"],
                value_hash=row._mapping["value_hash"],
                created_at=row._mapping["created_at"],
                updated_at=row._mapping["updated_at"],
                rotated_at=row._mapping["rotated_at"],
            )
            for row in rows
        ]

    def verify_secret(self, session: Session, *, secret_ref: str) -> SecretVerifyResult:
        validate_secret_ref(secret_ref)
        row = self._load_secret_row(session, secret_ref)
        if row["status"] != "active":
            raise SecretStoreError(f"secret is not active: {secret_ref}")

        master_key = get_required_master_key()
        decrypt_secret_value(
            secret_ref=secret_ref,
            ciphertext=_to_bytes(row["ciphertext"]),
            encryption_meta=_normalize_meta(row["encryption_meta_json"]),
            master_key=master_key,
        )
        return SecretVerifyResult(
            secret_ref=secret_ref,
            status=row["status"],
            readable=True,
            value_hash=row["value_hash"],
        )

    def get_secret_value(self, session: Session, *, secret_ref: str) -> str:
        validate_secret_ref(secret_ref)
        row = self._load_secret_row(session, secret_ref)
        if row["status"] != "active":
            raise SecretStoreError(f"secret is not active: {secret_ref}")

        return decrypt_secret_value(
            secret_ref=secret_ref,
            ciphertext=_to_bytes(row["ciphertext"]),
            encryption_meta=_normalize_meta(row["encryption_meta_json"]),
            master_key=get_required_master_key(),
        )

    def _load_secret_row(self, session: Session, secret_ref: str) -> dict[str, Any]:
        row = session.execute(
            text(
                """
                SELECT secret_ref, ciphertext, encryption_meta_json, value_hash, status
                FROM secrets
                WHERE secret_ref = :secret_ref
                """
            ),
            {"secret_ref": secret_ref},
        ).one_or_none()
        if row is None:
            raise SecretStoreError(f"secret ref does not exist: {secret_ref}")
        return dict(row._mapping)


def validate_secret_ref(secret_ref: str) -> None:
    if not SECRET_REF_PATTERN.match(secret_ref):
        raise SecretStoreError(
            "secret_ref must match secret://<namespace>/<service>/<name>"
        )
    if not secret_ref.startswith(SECRET_REF_PREFIX):
        raise SecretStoreError("P0 secret_ref must start with secret://rag/")


def get_required_master_key() -> str:
    master_key = (get_settings().secret_store_master_key or "").strip()
    if len(master_key) < 32:
        raise SecretStoreError(
            "SECRET_STORE_MASTER_KEY must be configured with at least 32 characters"
        )
    return master_key


def encrypt_secret_value(secret_ref: str, secret_value: str, master_key: str) -> EncryptedSecret:
    validate_secret_ref(secret_ref)
    if len(master_key.strip()) < 32:
        raise SecretStoreError("master key must contain at least 32 characters")

    salt = token_bytes(16)
    nonce = token_bytes(12)
    key = _derive_encryption_key(master_key, salt)
    ciphertext = AESGCM(key).encrypt(
        nonce,
        secret_value.encode("utf-8"),
        secret_ref.encode("utf-8"),
    )
    encryption_meta = {
        "algorithm": ENCRYPTION_ALGORITHM,
        "kdf": KDF_ALGORITHM,
        "key_id": KEY_ID,
        "salt": _b64_encode(salt),
        "nonce": _b64_encode(nonce),
        "associated_data": "secret_ref",
        "value_hash_algorithm": "HMAC-SHA256",
    }
    return EncryptedSecret(
        ciphertext=ciphertext,
        encryption_meta=encryption_meta,
        value_hash=_hash_secret_value(master_key, secret_value),
    )


def decrypt_secret_value(
    *,
    secret_ref: str,
    ciphertext: bytes,
    encryption_meta: dict[str, Any],
    master_key: str,
) -> str:
    validate_secret_ref(secret_ref)
    if encryption_meta.get("algorithm") != ENCRYPTION_ALGORITHM:
        raise SecretStoreError("unsupported secret encryption algorithm")
    if encryption_meta.get("kdf") != KDF_ALGORITHM:
        raise SecretStoreError("unsupported secret encryption kdf")

    salt = _b64_decode(str(encryption_meta["salt"]))
    nonce = _b64_decode(str(encryption_meta["nonce"]))
    key = _derive_encryption_key(master_key, salt)
    try:
        plaintext = AESGCM(key).decrypt(
            nonce,
            ciphertext,
            secret_ref.encode("utf-8"),
        )
    except InvalidTag as exc:
        raise SecretStoreError("secret cannot be decrypted with current master key") from exc
    return plaintext.decode("utf-8")


def _derive_encryption_key(master_key: str, salt: bytes) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=HKDF_INFO,
    ).derive(master_key.encode("utf-8"))


def _hash_secret_value(master_key: str, secret_value: str) -> str:
    return hmac.new(
        key=master_key.encode("utf-8"),
        msg=HASH_CONTEXT + secret_value.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()


def _normalize_meta(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return json.loads(value)
    raise SecretStoreError("secret encryption metadata is malformed")


def _to_bytes(value: object) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray | memoryview):
        return bytes(value)
    raise SecretStoreError("secret ciphertext is malformed")


def _b64_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")

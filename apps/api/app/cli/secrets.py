"""Secret Store 本地维护 CLI。

该 CLI 用于初始化前把 MinIO、JWT、模型 provider 等密钥写入 PostgreSQL secrets 表。
命令只打印 secret_ref、状态和 hash 前缀，避免把明文泄漏到终端历史或日志中。
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from app.db.session import session_scope
from app.modules.secrets.service import SecretListItem, SecretStoreError, SecretStoreService


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    service = SecretStoreService()

    try:
        if args.command == "put":
            secret_value = _read_secret_value(args)
            with session_scope() as session:
                result = service.put_secret(
                    session,
                    secret_ref=args.secret_ref,
                    secret_value=secret_value,
                )
            print(
                f"{result.action} {result.secret_ref} "
                f"status={result.status} hash={result.value_hash[:12]}"
            )
            return 0

        if args.command == "list":
            with session_scope() as session:
                items = service.list_secrets(session, include_deleted=args.include_deleted)
            _print_secret_list(items)
            return 0

        if args.command == "verify":
            with session_scope() as session:
                result = service.verify_secret(session, secret_ref=args.secret_ref)
            print(
                f"verified {result.secret_ref} "
                f"status={result.status} readable={str(result.readable).lower()} "
                f"hash={result.value_hash[:12]}"
            )
            return 0

        parser.error(f"unsupported command: {args.command}")
        return 2
    except (RuntimeError, SecretStoreError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli.secrets",
        description="Manage encrypted secrets stored in PostgreSQL.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    put_parser = subparsers.add_parser("put", help="Create or rotate a secret value.")
    put_parser.add_argument(
        "secret_ref",
        help="Secret ref, for example secret://rag/minio/access-key",
    )
    value_source = put_parser.add_mutually_exclusive_group()
    value_source.add_argument(
        "--stdin",
        action="store_true",
        help="Read the secret value from stdin.",
    )
    value_source.add_argument(
        "--value-env",
        metavar="ENV_NAME",
        help="Read the secret value from an environment variable.",
    )

    list_parser = subparsers.add_parser("list", help="List secret refs without values.")
    list_parser.add_argument(
        "--include-deleted",
        action="store_true",
        help="Include deleted secret rows.",
    )

    verify_parser = subparsers.add_parser(
        "verify",
        help="Verify a secret ref is active and decryptable.",
    )
    verify_parser.add_argument("secret_ref")

    return parser


def _read_secret_value(args: argparse.Namespace) -> str:
    if args.stdin:
        value = sys.stdin.read()
        value = value[:-1] if value.endswith("\n") else value
    elif args.value_env:
        value = _read_env_value(args.value_env)
    else:
        value = getpass.getpass("Secret value: ")

    if value == "":
        raise SecretStoreError("secret value cannot be empty")
    return value


def _read_env_value(name: str) -> str:
    # 优先读进程环境变量；读不到再解析 .env，便于本地不 source .env 也能初始化。
    value = os.environ.get(name)
    if value is not None:
        return value

    dotenv_value = _read_dotenv_value(name)
    if dotenv_value is not None:
        return dotenv_value

    raise SecretStoreError(f"environment variable is not set: {name}")


def _read_dotenv_value(name: str, env_file: Path = Path(".env")) -> str | None:
    if not env_file.exists():
        return None
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        parsed = _parse_dotenv_line(raw_line)
        if parsed and parsed[0] == name:
            return parsed[1]
    return None


def _parse_dotenv_line(raw_line: str) -> tuple[str, str] | None:
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
        return None
    if line.startswith("export "):
        line = line.removeprefix("export ").strip()
    key, value = line.split("=", maxsplit=1)
    key = key.strip()
    value = value.strip()
    if not key:
        return None
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value


def _print_secret_list(items: list[SecretListItem]) -> None:
    if not items:
        print("no secrets")
        return

    print("secret_ref\tstatus\tscope\tupdated_at\trotated_at\thash")
    for item in items:
        print(
            "\t".join(
                [
                    item.secret_ref,
                    item.status,
                    f"{item.scope_type}/{item.scope_id}",
                    _format_nullable(item.updated_at),
                    _format_nullable(item.rotated_at),
                    item.value_hash[:12],
                ]
            )
        )


def _format_nullable(value: object) -> str:
    return "-" if value is None else str(value)


if __name__ == "__main__":
    raise SystemExit(main())

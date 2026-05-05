from __future__ import annotations

import argparse
import getpass
import os
import sys
from collections.abc import Sequence

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
        value = os.environ.get(args.value_env)
        if value is None:
            raise SecretStoreError(f"environment variable is not set: {args.value_env}")
    else:
        value = getpass.getpass("Secret value: ")

    if value == "":
        raise SecretStoreError("secret value cannot be empty")
    return value


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

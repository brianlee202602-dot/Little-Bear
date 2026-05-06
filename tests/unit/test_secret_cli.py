from __future__ import annotations

from argparse import Namespace

from app.cli.secrets import _build_parser, _read_secret_value


def test_secret_cli_reads_value_from_dotenv(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SECRET_INIT_MINIO_ACCESS_KEY", raising=False)
    tmp_path.joinpath(".env").write_text(
        "SECRET_INIT_MINIO_ACCESS_KEY=minioadmin\n",
        encoding="utf-8",
    )

    value = _read_secret_value(Namespace(stdin=False, value_env="SECRET_INIT_MINIO_ACCESS_KEY"))

    assert value == "minioadmin"


def test_secret_cli_prefers_process_env_over_dotenv(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SECRET_INIT_MINIO_ACCESS_KEY", "from-env")
    tmp_path.joinpath(".env").write_text(
        "SECRET_INIT_MINIO_ACCESS_KEY=from-dotenv\n",
        encoding="utf-8",
    )

    value = _read_secret_value(Namespace(stdin=False, value_env="SECRET_INIT_MINIO_ACCESS_KEY"))

    assert value == "from-env"


def test_secret_cli_put_accepts_qdrant_secret_ref() -> None:
    args = _build_parser().parse_args(
        [
            "put",
            "secret://rag/qdrant/api-key",
            "--value-env",
            "SECRET_INIT_QDRANT_API_KEY",
        ]
    )

    assert args.command == "put"
    assert args.secret_ref == "secret://rag/qdrant/api-key"
    assert args.value_env == "SECRET_INIT_QDRANT_API_KEY"

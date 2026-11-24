import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app


def _settings(**kwargs: object) -> Settings:
    return Settings(_env_file=None, **kwargs)  # type: ignore[arg-type]


def test_origins_parsed_from_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://a.test, https://b.test/ ,")
    assert _settings().allowed_origins == ["http://a.test", "https://b.test"]


def test_wildcard_origin_rejected() -> None:
    with pytest.raises(ValidationError):
        _settings(allowed_origins=["*"])


def test_database_url_is_not_exposed_in_repr() -> None:
    s = _settings(database_url="postgresql+psycopg://u:supersecret@db/agrios")
    assert "supersecret" not in repr(s)


def test_docs_disabled_in_production() -> None:
    app = create_app(_settings(app_env="production", jwt_secret="p" * 40))
    assert app.docs_url is None
    assert app.openapi_url is None


def test_docs_enabled_in_development() -> None:
    app = create_app(_settings(app_env="development"))
    assert app.docs_url == "/api/v1/docs"


def test_docs_opt_in_in_production() -> None:
    app = create_app(_settings(app_env="production", jwt_secret="p" * 40, api_docs_enabled=True))
    assert app.docs_url == "/api/v1/docs"
    assert app.openapi_url == "/api/v1/openapi.json"


@pytest.mark.parametrize("scheme", ["postgres://", "postgresql://"])
def test_hosted_database_url_uses_psycopg_driver(scheme: str) -> None:
    s = _settings(database_url=f"{scheme}u:pw@db.internal:5432/agrios")
    assert s.database_url is not None
    assert s.database_url.get_secret_value() == "postgresql+psycopg://u:pw@db.internal:5432/agrios"


def test_explicit_driver_url_is_unchanged() -> None:
    url = "postgresql+psycopg://u:pw@127.0.0.1:54330/agrios"
    s = _settings(database_url=url)
    assert s.database_url is not None
    assert s.database_url.get_secret_value() == url


def test_env_file_and_relative_paths_are_anchored_to_backend_dir() -> None:
    from app.core.config import BACKEND_DIR, ENV_FILE

    assert ENV_FILE == BACKEND_DIR / ".env"
    s = _settings(storage_path="./var/uploads")
    assert s.storage_path == (BACKEND_DIR / "var" / "uploads").resolve()
    assert _settings(storage_path="C:/abs/up").storage_path.is_absolute()


def test_test_database_targets_are_detected() -> None:
    assert _settings(
        database_url="postgresql+psycopg://u@127.0.0.1:54329/x"
    ).database_target_is_test
    assert _settings(
        database_url="postgresql+psycopg://u@h:5432/agrios_test"
    ).database_target_is_test
    assert not _settings(
        database_url="postgresql+psycopg://u@h:5432/agrios"
    ).database_target_is_test

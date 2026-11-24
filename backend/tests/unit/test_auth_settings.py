import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _settings(**kwargs: object) -> Settings:
    return Settings(_env_file=None, **kwargs)  # type: ignore[arg-type]


def test_production_requires_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        _settings(app_env="production")


def test_short_jwt_secret_rejected() -> None:
    with pytest.raises(ValidationError, match="32"):
        _settings(jwt_secret="short")


def test_jwt_secret_not_in_repr() -> None:
    s = _settings(jwt_secret="x" * 40)
    assert "x" * 40 not in repr(s)

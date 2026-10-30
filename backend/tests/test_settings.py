from pathlib import Path

import pytest

from daftar.settings import Settings, SettingsError

ENV = {
    "DATABASE_URL": "postgresql://daftar:geheim-db@db.example:5433/daftar",
    "JWT_SECRET": "j" * 32,
}


def test_reads_required_and_optional_variables() -> None:
    s = Settings.from_env(
        {
            **ENV,
            "ADMIN_EMAIL": " Omar@Example.TN ",
            "ADMIN_PASSWORD": "admin-passwort-1",
            "ADMIN_RESET_PASSWORD": "true",
            "PORT": "9000",
            "LANDING_DIR": "/srv/landing",
            "WEB_DIR": "/srv/web",
        }
    )
    assert s.database_url == "postgresql+psycopg://daftar:geheim-db@db.example:5433/daftar"
    assert s.admin_email == "omar@example.tn"
    assert s.admin_password == "admin-passwort-1"
    assert s.admin_reset_password is True
    assert s.port == 9000
    assert s.landing_dir == Path("/srv/landing")
    assert s.web_dir == Path("/srv/web")


def test_defaults() -> None:
    s = Settings.from_env(ENV)
    assert (s.admin_email, s.admin_password, s.admin_reset_password, s.port) == (None, None, False, 8080)
    assert s.landing_dir.name == "landing"
    assert s.web_dir.parts[-2:] == ("web", "build")


@pytest.mark.parametrize("missing", ["DATABASE_URL", "JWT_SECRET"])
def test_required_variables(missing: str) -> None:
    env = {k: v for k, v in ENV.items() if k != missing}
    with pytest.raises(SettingsError, match=missing):
        Settings.from_env(env)


def test_jwt_secret_needs_32_characters() -> None:
    with pytest.raises(SettingsError, match="JWT_SECRET"):
        Settings.from_env({**ENV, "JWT_SECRET": "j" * 31})


@pytest.mark.parametrize("port", ["0", "70000", "abc"])
def test_invalid_port(port: str) -> None:
    with pytest.raises(SettingsError, match="PORT"):
        Settings.from_env({**ENV, "PORT": port})


def test_rejects_non_postgres_urls() -> None:
    with pytest.raises(SettingsError, match="DATABASE_URL"):
        Settings.from_env({**ENV, "DATABASE_URL": "mysql://x@y/z"})


def test_repr_masks_every_secret() -> None:
    s = Settings.from_env({**ENV, "ADMIN_EMAIL": "omar@example.tn", "ADMIN_PASSWORD": "admin-passwort-1"})
    text = repr(s) + str(s)
    for secret in ("geheim-db", "j" * 32, "admin-passwort-1"):
        assert secret not in text
    assert "omar@example.tn" in text
    assert "db.example:5433" in text


def test_base_domain_and_flouci_keys() -> None:
    s = Settings.from_env(ENV)
    assert s.base_domain == "daftar.omarfourati.de"
    assert (s.flouci_app_token, s.flouci_app_secret) == (None, None)
    s = Settings.from_env(
        {**ENV, "BASE_DOMAIN": " Daftar.Example.TN ", "FLOUCI_APP_TOKEN": "tok-flouci-1", "FLOUCI_APP_SECRET": "sec-flouci-2"}
    )
    assert s.base_domain == "daftar.example.tn"
    assert (s.flouci_app_token, s.flouci_app_secret) == ("tok-flouci-1", "sec-flouci-2")
    assert "tok-flouci-1" not in repr(s) and "sec-flouci-2" not in repr(s)
    assert "daftar.example.tn" in repr(s)

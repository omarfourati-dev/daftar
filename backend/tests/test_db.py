"""The engine itself (no database needed): unexpected database errors must not log personal data."""

from sqlalchemy.exc import IntegrityError

from daftar.db import make_engine


def test_sql_parameters_never_reach_error_messages_or_logs() -> None:
    """Security review N1: names, phone numbers and hashes in ``[parameters: …]`` of a logged IntegrityError."""
    engine = make_engine("postgresql+psycopg://daftar:secret@localhost:1/none")
    try:
        assert engine.hide_parameters is True
        error = IntegrityError("INSERT INTO patient (last_name, phone) VALUES (%(a)s, %(b)s)",
                               {"a": "Ben Salah", "b": "+216٢٠١٢٣٤٥٦"}, Exception("check violation"),
                               hide_parameters=engine.hide_parameters)
        assert "Ben Salah" not in str(error) and "+216" not in str(error)
        assert "hidden due to hide_parameters" in str(error)
    finally:
        engine.dispose()

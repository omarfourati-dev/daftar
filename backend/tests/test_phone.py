import pytest
from pydantic import ValidationError

from daftar.phone import InvalidPhone, OptionalPhone, Phone, normalize_phone, phone_digits
from daftar.schemas import ApiModel


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        ("20 123 456", "+21620123456"),
        ("20123456", "+21620123456"),
        ("+216 20123456", "+21620123456"),
        ("+216 20 123 456", "+21620123456"),
        ("0021620123456", "+21620123456"),
        ("00216 20.123.456", "+21620123456"),
        ("216 20 123 456", "+21620123456"),
        ("(+216) 20-123-456", "+21620123456"),
        ("+216 20 123 456", "+21620123456"),
        ("+21600000001", "+21600000001"),  # demo numbers: the prefix 00 does not exist in Tunisia
        ("+33 6 12 34 56 78", "+33612345678"),
        ("0033612345678", "+33612345678"),
        ("+49 151 23456789", "+4915123456789"),
    ],
)
def test_normalizes_to_e164(raw: str, want: str) -> None:
    assert normalize_phone(raw) == want


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "2012345",  # 7 digits
        "201234567",  # 9 digits without country code
        "+216 2012345",  # too short for Tunisia
        "+216 201234567",  # too long for Tunisia
        "06 12 34 56 78",  # foreign number without +
        "+0612345678",
        "+1234567",  # too short for E.164
        "+1234567890123456",  # too long for E.164
        "20 12a 456",
        "++21620123456",
    ],
)
def test_rejects_invalid_numbers(raw: str) -> None:
    with pytest.raises(InvalidPhone):
        normalize_phone(raw)


def test_phone_digits_for_whatsapp_links() -> None:
    assert phone_digits("+21620123456") == "21620123456"


class _Form(ApiModel):
    phone: Phone
    other: OptionalPhone = None


def test_pydantic_types_normalize_and_reject() -> None:
    form = _Form.model_validate({"phone": "20 123 456", "other": "  "})
    assert (form.phone, form.other) == ("+21620123456", None)
    assert _Form.model_validate({"phone": "20123456", "other": "+33612345678"}).other == "+33612345678"
    with pytest.raises(ValidationError, match="invalid_phone"):
        _Form.model_validate({"phone": "123"})

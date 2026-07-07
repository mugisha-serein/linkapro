from decimal import Decimal

import pytest

from domain.vendors.package_rules import PackageValidationError, validate_service_package_rules


def valid_rules_payload(**overrides):
    data = {
        "name": "Standard event package",
        "description": "A clear standard event package with defined deliverables.",
        "price": Decimal("5000.00"),
        "package_tier": "standard",
    }
    data.update(overrides)
    return data


def test_package_rules_reject_nan_infinity_and_excessive_scale():
    for price in [Decimal("NaN"), Decimal("Infinity"), Decimal("10.123")]:
        with pytest.raises(PackageValidationError) as exc_info:
            validate_service_package_rules(**valid_rules_payload(price=price))

        assert "price" in exc_info.value.field_errors


def test_package_rules_reject_too_large_price_and_control_characters():
    with pytest.raises(PackageValidationError) as exc_info:
        validate_service_package_rules(
            **valid_rules_payload(
                name="Bad\x00package",
                price=Decimal("10000000000.00"),
            )
        )

    assert "name" in exc_info.value.field_errors
    assert "price" in exc_info.value.field_errors


def test_package_rules_preserve_tier_minimums_and_misleading_term_rules():
    with pytest.raises(PackageValidationError) as exc_info:
        validate_service_package_rules(
            **valid_rules_payload(
                name="Premium standard package",
                description="Short but clear standard package description.",
                package_tier="standard",
            )
        )

    assert "name" in exc_info.value.field_errors

    with pytest.raises(PackageValidationError) as gold_error:
        validate_service_package_rules(
            **valid_rules_payload(
                name="Gold coordination",
                description=(
                    "A complete gold package with planning, coordination, delivery, and guaranteed approval."
                ),
                price=Decimal("100000.00"),
                package_tier="gold",
            )
        )

    assert "description" in gold_error.value.field_errors


def test_package_rules_normalize_tier_before_validation():
    validate_service_package_rules(
        **valid_rules_payload(
            package_tier=" Premier ",
            description="A complete premier event package with setup and vendor coordination.",
            price=Decimal("50000.00"),
        )
    )

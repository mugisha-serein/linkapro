from __future__ import annotations

from dataclasses import fields
from types import NoneType
from typing import get_args, get_type_hints
import uuid

from application.vendors.profile.commands import UpdateVendorProfileCommand
from application.vendors.shared.commands import OMITTED, AuthenticatedActor, OmittedValue


STRING_UPDATE_FIELDS = (
    "business_name",
    "category",
    "description",
    "service_area",
    "contact_email",
    "contact_phone",
)
NULLABLE_STRING_UPDATE_FIELDS = ("custom_category", "website")


def test_omitted_value_is_a_generic_union_with_the_existing_sentinel_type():
    omitted_type = type(OMITTED)

    assert set(get_args(OmittedValue[int])) == {int, omitted_type}
    assert set(get_args(OmittedValue[str])) == {str, omitted_type}
    assert set(get_args(OmittedValue[str | None])) == {
        str,
        NoneType,
        omitted_type,
    }


def test_update_vendor_profile_annotations_preserve_each_real_field_type():
    hints = get_type_hints(UpdateVendorProfileCommand)
    omitted_type = type(OMITTED)

    for field_name in STRING_UPDATE_FIELDS:
        assert set(get_args(hints[field_name])) == {str, omitted_type}
        assert object not in get_args(hints[field_name])

    for field_name in NULLABLE_STRING_UPDATE_FIELDS:
        assert set(get_args(hints[field_name])) == {
            str,
            NoneType,
            omitted_type,
        }
        assert object not in get_args(hints[field_name])


def test_all_update_field_defaults_preserve_the_single_omitted_sentinel():
    command_fields = {field.name: field for field in fields(UpdateVendorProfileCommand)}

    for field_name in STRING_UPDATE_FIELDS + NULLABLE_STRING_UPDATE_FIELDS:
        assert command_fields[field_name].default is OMITTED


def test_omitted_and_explicit_nullable_values_remain_distinct_at_runtime():
    command = UpdateVendorProfileCommand(
        actor=AuthenticatedActor(user_id=uuid.uuid4()),
        vendor_id=uuid.uuid4(),
        expected_version=4,
        business_name="Updated Vendor",
        custom_category=None,
        website=None,
    )

    assert command.business_name == "Updated Vendor"
    assert command.custom_category is None
    assert command.website is None
    assert command.category is OMITTED
    assert command.description is OMITTED
    assert command.service_area is OMITTED
    assert command.contact_email is OMITTED
    assert command.contact_phone is OMITTED


def test_default_construction_keeps_update_semantics_unchanged():
    actor = AuthenticatedActor(user_id=uuid.uuid4())
    vendor_id = uuid.uuid4()

    command = UpdateVendorProfileCommand(
        actor=actor,
        vendor_id=vendor_id,
        expected_version=0,
    )

    assert command.actor is actor
    assert command.vendor_id == vendor_id
    assert command.expected_version == 0
    for field_name in STRING_UPDATE_FIELDS + NULLABLE_STRING_UPDATE_FIELDS:
        assert getattr(command, field_name) is OMITTED
    assert repr(OMITTED) == "OMITTED"

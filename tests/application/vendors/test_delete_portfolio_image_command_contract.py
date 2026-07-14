from __future__ import annotations

from dataclasses import MISSING, fields
import inspect
import uuid

import pytest

from application.vendors.portfolio.commands import DeletePortfolioImageCommand
from application.vendors.shared.commands import AuthenticatedActor
from application.vendors.shared.handlers import VendorCommandHandlers


def test_delete_portfolio_image_command_contains_only_current_use_case_inputs():
    command_fields = fields(DeletePortfolioImageCommand)

    assert tuple(field.name for field in command_fields) == (
        "actor",
        "vendor_id",
        "image_id",
        "expected_version",
    )
    assert all(field.default is MISSING for field in command_fields)
    assert "deleted_by_id" not in DeletePortfolioImageCommand.__annotations__


def test_delete_portfolio_image_command_rejects_removed_deleted_by_id_argument():
    with pytest.raises(TypeError, match="deleted_by_id"):
        DeletePortfolioImageCommand(
            actor=AuthenticatedActor(user_id=uuid.uuid4()),
            vendor_id=uuid.uuid4(),
            image_id=uuid.uuid4(),
            expected_version=3,
            deleted_by_id=uuid.uuid4(),
        )


def test_delete_portfolio_image_command_runtime_behavior_is_unchanged_without_attribution():
    actor = AuthenticatedActor(user_id=uuid.uuid4())
    vendor_id = uuid.uuid4()
    image_id = uuid.uuid4()

    command = DeletePortfolioImageCommand(
        actor=actor,
        vendor_id=vendor_id,
        image_id=image_id,
        expected_version=4,
    )

    assert command.actor is actor
    assert command.vendor_id == vendor_id
    assert command.image_id == image_id
    assert command.expected_version == 4
    assert not hasattr(command, "deleted_by_id")


def test_delete_portfolio_image_handler_accepts_the_reduced_command_contract():
    signature = inspect.signature(VendorCommandHandlers.delete_portfolio_image)

    assert tuple(signature.parameters) == ("self", "cmd")
    assert signature.parameters["cmd"].annotation in {
        DeletePortfolioImageCommand,
        "DeletePortfolioImageCommand",
    }

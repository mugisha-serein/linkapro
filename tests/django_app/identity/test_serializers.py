import uuid

from django_app.identity.shared.serializers import (
    AssignRoleSerializer,
    ResetPasswordSerializer,
    SuspendAccountSerializer,
)
from domain.identity.account import AccountRole
from domain.identity.credentials import PlainPassword
from domain.identity.shared.security_reason import SecurityReason
from application.identity.recovery.reset_password_command import (
    PasswordResetTokenInput,
    SecurityMetadataHash,
)


def test_assign_role_serializer_builds_typed_command_at_boundary():
    actor_id = uuid.uuid4()
    target_user_id = uuid.uuid4()
    serializer = AssignRoleSerializer(
        data={
            "new_role": "vendor",
            "reason": " support request ",
        }
    )

    assert serializer.is_valid(), serializer.errors
    command = serializer.to_command(actor_id=actor_id, target_user_id=target_user_id)

    assert command.actor_id == actor_id
    assert command.target_user_id == target_user_id
    assert command.new_role is AccountRole.VENDOR
    assert isinstance(command.reason, SecurityReason)
    assert command.reason.value == "support request"


def test_suspend_account_serializer_builds_typed_reason_at_boundary():
    actor_id = uuid.uuid4()
    target_user_id = uuid.uuid4()
    serializer = SuspendAccountSerializer(data={"reason": "terms violation"})

    assert serializer.is_valid(), serializer.errors
    command = serializer.to_command(actor_id=actor_id, target_user_id=target_user_id)

    assert command.actor_id == actor_id
    assert command.target_user_id == target_user_id
    assert isinstance(command.reason, SecurityReason)
    assert command.reason.value == "terms violation"


def test_account_administration_serializers_reject_secret_like_reasons():
    assign_serializer = AssignRoleSerializer(
        data={
            "new_role": "vendor",
            "reason": "reset token leaked",
        }
    )
    suspend_serializer = SuspendAccountSerializer(data={"reason": "password exposed"})

    assert not assign_serializer.is_valid()
    assert not suspend_serializer.is_valid()
    assert "reason" in assign_serializer.errors
    assert "reason" in suspend_serializer.errors


def test_reset_password_serializer_builds_typed_command_with_hashed_metadata():
    serializer = ResetPasswordSerializer(
        data={
            "token": "raw-reset-token",
            "new_password": "ValidPass1!",
        }
    )

    assert serializer.is_valid(), serializer.errors
    command = serializer.to_command(client_ip_hash="a" * 64, user_agent_hash="b" * 64)

    assert isinstance(command.token, PasswordResetTokenInput)
    assert isinstance(command.new_password, PlainPassword)
    assert isinstance(command.client_ip_hash, SecurityMetadataHash)
    assert isinstance(command.user_agent_hash, SecurityMetadataHash)
    assert command.client_ip_hash.value == "a" * 64
    assert command.user_agent_hash.value == "b" * 64
    assert "raw-reset-token" not in repr(command)
    assert "ValidPass1!" not in repr(command)

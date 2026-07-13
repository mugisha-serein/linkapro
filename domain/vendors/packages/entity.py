from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import ClassVar, Optional

from domain.shared.utils import utc_now
from domain.vendors.packages.errors import InvalidPackageTransition, PackageValidationError
from domain.vendors.packages.events import (
    ServicePackageActivated,
    ServicePackageApproved,
    ServicePackageCreated,
    ServicePackageDeactivated,
    ServicePackageRejected,
    ServicePackageSubmittedForApproval,
    ServicePackageUpdated,
)
from domain.vendors.packages.rules import mark_vendor_package_public_edit, package_public_fields_changed, validate_service_package_rules
from domain.vendors.shared.aggregate import (
    DomainAggregate,
    _normalize_bool,
    _normalize_currency_value,
    _normalize_datetime,
    _normalize_enum_value,
    _normalize_optional_text,
    _normalize_price,
    _normalize_text,
    _normalize_uuid,
    _normalize_version,
    _validated_transition_reason,
)
from domain.vendors.shared.validation import TEXT_LIMITS, add_error

class PackageTier(str, Enum):
    STANDARD = "standard"
    PREMIER = "premier"
    GOLD = "gold"

class PackageApprovalStatus(str, Enum):
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"

class CurrencyCode(str, Enum):
    RWF = "RWF"
    USD = "USD"
    EUR = "EUR"
    KES = "KES"
    GHS = "GHS"
    NGN = "NGN"

@dataclass
class ServicePackage(DomainAggregate):
    _protected_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "approval_status",
            "rejection_reason",
            "is_active",
            "is_deleted",
            "deleted_at",
            "version",
        }
    )

    id: uuid.UUID
    vendor_id: uuid.UUID
    name: str
    description: str
    price: Decimal
    currency: str = "RWF"
    package_tier: str = "standard"
    approval_status: str = "waiting_approval"
    rejection_reason: Optional[str] = None
    is_active: bool = False
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    last_approved_at: Optional[datetime] = None
    last_vendor_public_edit_at: Optional[datetime] = None
    next_vendor_edit_allowed_at: Optional[datetime] = None
    version: int = 0
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    _events: list = field(default_factory=list, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._init_domain_state()
        self.validate_invariants()
        self._lock_state()

    @classmethod
    def create(
        cls,
        *,
        vendor_id: uuid.UUID,
        name: str,
        description: str,
        price: Decimal,
        currency: str = "RWF",
        package_tier: str = PackageTier.STANDARD.value,
    ) -> "ServicePackage":
        package = cls(
            id=uuid.uuid4(),
            vendor_id=vendor_id,
            name=name,
            description=description,
            price=price,
            currency=currency,
            package_tier=package_tier,
            approval_status=PackageApprovalStatus.WAITING_APPROVAL.value,
            is_active=False,
        )
        package._record(
            ServicePackageCreated(
                package_id=package.id,
                vendor_id=package.vendor_id,
                occurred_at=package.created_at,
                aggregate_id=package.id,
                aggregate_version=package.version,
            )
        )
        return package

    @classmethod
    def rehydrate(cls, **kwargs) -> "ServicePackage":
        cls._validate_rehydrate_input(kwargs)
        package = cls(**kwargs)
        package._validate_strict_rehydration()
        package._events.clear()
        return package

    @classmethod
    def _validate_rehydrate_input(cls, kwargs: dict) -> None:
        errors: dict[str, list[str]] = {}
        approval_status = kwargs.get("approval_status", PackageApprovalStatus.WAITING_APPROVAL.value)
        if isinstance(approval_status, PackageApprovalStatus):
            approval_status = approval_status.value
        if approval_status == PackageApprovalStatus.APPROVED.value and kwargs.get("last_approved_at") is None:
            add_error(errors, "last_approved_at", "Approved packages require last_approved_at.")
        if kwargs.get("is_deleted") is True and kwargs.get("deleted_at") is None:
            add_error(errors, "deleted_at", "Deleted packages require deleted_at.")
        if errors:
            raise PackageValidationError(field_errors=errors)

    def _validate_strict_rehydration(self) -> None:
        errors: dict[str, list[str]] = {}
        if self.approval_status == PackageApprovalStatus.APPROVED.value and self.last_approved_at is None:
            add_error(errors, "last_approved_at", "Approved packages require last_approved_at.")
        if self.is_deleted and self.deleted_at is None:
            add_error(errors, "deleted_at", "Deleted packages require deleted_at.")
        if errors:
            raise PackageValidationError(field_errors=errors)

    def validate_invariants(self) -> None:
        errors: dict[str, list[str]] = {}
        self.id = _normalize_uuid(self.id, "id", errors)
        self.vendor_id = _normalize_uuid(self.vendor_id, "vendor_id", errors)
        self.name = _normalize_text(self.name, "name", TEXT_LIMITS["package_name"], errors)
        self.description = _normalize_text(
            self.description,
            "description",
            TEXT_LIMITS["package_description"],
            errors,
        )
        self.price = _normalize_price(self.price, errors)
        self.currency = _normalize_currency_value(self.currency, errors)
        self.package_tier = _normalize_enum_value(PackageTier, self.package_tier, "package_tier", errors)
        self.approval_status = _normalize_enum_value(
            PackageApprovalStatus,
            self.approval_status,
            "approval_status",
            errors,
        )
        self.rejection_reason = _normalize_optional_text(
            self.rejection_reason,
            "rejection_reason",
            TEXT_LIMITS["rejection_reason"],
            errors,
        )
        self.created_at = _normalize_datetime(self.created_at, "created_at", errors, required=True)
        self.updated_at = _normalize_datetime(self.updated_at, "updated_at", errors, required=True)
        self.deleted_at = _normalize_datetime(self.deleted_at, "deleted_at", errors)
        self.last_approved_at = _normalize_datetime(self.last_approved_at, "last_approved_at", errors)
        self.last_vendor_public_edit_at = _normalize_datetime(
            self.last_vendor_public_edit_at,
            "last_vendor_public_edit_at",
            errors,
        )
        self.next_vendor_edit_allowed_at = _normalize_datetime(
            self.next_vendor_edit_allowed_at,
            "next_vendor_edit_allowed_at",
            errors,
        )
        self.version = _normalize_version(self.version, errors)
        self.is_active = _normalize_bool(self.is_active, "is_active", errors)
        self.is_deleted = _normalize_bool(self.is_deleted, "is_deleted", errors)

        if self.is_deleted and self.is_active:
            add_error(errors, "is_active", "Deleted packages must be inactive.")
        if self.is_deleted and self.deleted_at is None:
            add_error(errors, "deleted_at", "Deleted packages require deleted_at.")
        if self.approval_status == PackageApprovalStatus.APPROVED.value and self.last_approved_at is None:
            add_error(errors, "last_approved_at", "Approved packages require last_approved_at.")
        if self.approval_status == PackageApprovalStatus.WAITING_APPROVAL.value and self.is_active:
            add_error(errors, "is_active", "Waiting approval packages cannot be active.")
        if self.approval_status == PackageApprovalStatus.REJECTED.value:
            if self.is_active:
                add_error(errors, "is_active", "Rejected packages cannot be active.")
            if not self.rejection_reason:
                add_error(errors, "rejection_reason", "Rejected packages require rejection_reason.")
        if self.approval_status != PackageApprovalStatus.REJECTED.value and self.rejection_reason:
            add_error(errors, "rejection_reason", "Only rejected packages can have rejection metadata.")
        if self.last_vendor_public_edit_at and self.next_vendor_edit_allowed_at:
            if self.next_vendor_edit_allowed_at < self.last_vendor_public_edit_at:
                add_error(errors, "next_vendor_edit_allowed_at", "Next edit time cannot be before the last edit.")

        try:
            validate_service_package_rules(
                name=self.name,
                description=self.description,
                price=self.price,
                package_tier=self.package_tier,
            )
        except PackageValidationError as exc:
            for field_name, messages in exc.field_errors.items():
                for message in messages:
                    add_error(errors, field_name, message)

        if errors:
            raise PackageValidationError(field_errors=errors)

    def update_details(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        price: Optional[Decimal] = None,
        currency: Optional[str] = None,
        package_tier: Optional[str] = None,
    ) -> None:
        if self.is_deleted:
            raise InvalidPackageTransition("Deleted packages cannot be edited.")
        next_name = self.name if name is None else name
        next_description = self.description if description is None else description
        next_price = self.price if price is None else price
        next_currency = self.currency if currency is None else currency
        next_tier = self.package_tier if package_tier is None else package_tier
        public_changed = package_public_fields_changed(
            self,
            name=next_name,
            description=next_description,
            price=next_price,
            currency=next_currency,
            package_tier=next_tier,
        )
        if not public_changed:
            return
        now = utc_now()
        markers = mark_vendor_package_public_edit(self, now=now, public_fields_changed=True)
        candidate = replace(
            self,
            name=next_name,
            description=next_description,
            price=next_price,
            currency=next_currency,
            package_tier=next_tier,
            updated_at=now,
            **markers,
        )
        self._commit_candidate(
            candidate,
            lambda version: ServicePackageUpdated(
                package_id=self.id,
                vendor_id=self.vendor_id,
                occurred_at=candidate.updated_at,
                aggregate_id=self.id,
                aggregate_version=version,
            ),
        )

    def submit_for_approval(self) -> None:
        if self.is_deleted:
            raise InvalidPackageTransition("Deleted packages cannot be submitted.")
        if self.approval_status == PackageApprovalStatus.WAITING_APPROVAL.value:
            return
        candidate = replace(
            self,
            approval_status=PackageApprovalStatus.WAITING_APPROVAL.value,
            rejection_reason=None,
            is_active=False,
            updated_at=utc_now(),
        )
        self._commit_candidate(
            candidate,
            lambda version: ServicePackageSubmittedForApproval(
                package_id=self.id,
                vendor_id=self.vendor_id,
                occurred_at=candidate.updated_at,
                aggregate_id=self.id,
                aggregate_version=version,
            ),
        )

    def approve(self) -> None:
        if self.is_deleted:
            raise InvalidPackageTransition("Deleted packages cannot be approved.")
        if self.approval_status != PackageApprovalStatus.WAITING_APPROVAL.value:
            raise InvalidPackageTransition("Only waiting packages can be approved.")
        now = utc_now()
        candidate = replace(
            self,
            approval_status=PackageApprovalStatus.APPROVED.value,
            rejection_reason=None,
            last_approved_at=now,
            is_active=False,
            updated_at=now,
        )
        self._commit_candidate(
            candidate,
            lambda version: ServicePackageApproved(
                package_id=self.id,
                vendor_id=self.vendor_id,
                occurred_at=now,
                aggregate_id=self.id,
                aggregate_version=version,
            ),
        )

    def reject(self, reason: str) -> None:
        if self.is_deleted:
            raise InvalidPackageTransition("Deleted packages cannot be rejected.")
        if self.approval_status != PackageApprovalStatus.WAITING_APPROVAL.value:
            raise InvalidPackageTransition("Only waiting packages can be rejected.")
        clean_reason = _validated_transition_reason(reason, "rejection_reason", PackageValidationError)
        candidate = replace(
            self,
            approval_status=PackageApprovalStatus.REJECTED.value,
            rejection_reason=clean_reason,
            is_active=False,
            updated_at=utc_now(),
        )
        self._commit_candidate(
            candidate,
            lambda version: ServicePackageRejected(
                package_id=self.id,
                vendor_id=self.vendor_id,
                reason=clean_reason,
                occurred_at=candidate.updated_at,
                aggregate_id=self.id,
                aggregate_version=version,
            ),
        )

    def restore_to_waiting_approval(self) -> None:
        if self.is_deleted:
            raise InvalidPackageTransition("Deleted packages cannot be restored.")
        if self.approval_status == PackageApprovalStatus.WAITING_APPROVAL.value and not self.is_active:
            return
        candidate = replace(
            self,
            approval_status=PackageApprovalStatus.WAITING_APPROVAL.value,
            rejection_reason=None,
            is_active=False,
            updated_at=utc_now(),
        )
        self._commit_candidate(
            candidate,
            lambda version: ServicePackageSubmittedForApproval(
                package_id=self.id,
                vendor_id=self.vendor_id,
                occurred_at=candidate.updated_at,
                aggregate_id=self.id,
                aggregate_version=version,
            ),
        )

    def deactivate(self) -> None:
        if self.is_deleted and not self.is_active:
            return
        candidate = replace(
            self,
            is_active=False,
            is_deleted=True,
            deleted_at=utc_now(),
            updated_at=utc_now(),
        )
        self._commit_candidate(
            candidate,
            lambda version: ServicePackageDeactivated(
                package_id=self.id,
                vendor_id=self.vendor_id,
                occurred_at=candidate.updated_at,
                aggregate_id=self.id,
                aggregate_version=version,
            ),
        )

    def activate(self) -> None:
        if self.is_deleted:
            raise InvalidPackageTransition("Deleted packages cannot be activated.")
        if self.approval_status != PackageApprovalStatus.APPROVED.value:
            raise InvalidPackageTransition("Only approved packages can be activated.")
        if self.is_active:
            return
        candidate = replace(self, is_active=True, updated_at=utc_now())
        self._commit_candidate(
            candidate,
            lambda version: ServicePackageActivated(
                package_id=self.id,
                vendor_id=self.vendor_id,
                occurred_at=candidate.updated_at,
                aggregate_id=self.id,
                aggregate_version=version,
            ),
        )

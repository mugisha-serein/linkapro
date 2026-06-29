from domain.shared.utils import utc_now
from domain.vendors.package_edit_policy import (
    ensure_vendor_package_edit_allowed,
    mark_vendor_package_public_edit,
    package_public_fields_changed,
)
from domain.vendors.package_rules import validate_service_package_rules

from .commands import UpdateServicePackageCommand
from .dtos import ServicePackageDTO
from .handlers import VendorCommandHandlers


class VendorCooldownCommandHandlers(VendorCommandHandlers):
    def update_service_package(self, cmd: UpdateServicePackageCommand) -> ServicePackageDTO:
        package = self.package_repo.get_by_id(cmd.package_id)
        self._assert_package_owned(package, cmd.vendor_id)

        changed = package_public_fields_changed(
            package,
            name=cmd.name,
            description=cmd.description,
            price=cmd.price,
            currency=cmd.currency,
            package_tier=cmd.package_tier,
        )
        now = utc_now()
        ensure_vendor_package_edit_allowed(package, public_fields_changed=changed, now=now)

        package.update_details(cmd.name, cmd.description, cmd.price, cmd.currency, cmd.package_tier)
        validate_service_package_rules(
            name=package.name,
            description=package.description,
            price=package.price,
            package_tier=package.package_tier,
        )
        mark_vendor_package_public_edit(package, now=now, public_fields_changed=changed)
        saved = self.package_repo.save(package)
        return self._to_package_dto(saved)

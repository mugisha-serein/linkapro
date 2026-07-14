from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch
import uuid

from application.vendors.packages.dtos import ServicePackageDTO
from application.vendors.packages.queries import ListServicePackagesQuery
from application.vendors.shared.dtos import PageDTO
from django_app.vendors.views.packages import ServicePackageListView


def test_package_list_view_passes_q_as_search_text():
    user_id = uuid.uuid4()
    vendor_id = uuid.uuid4()
    package_id = uuid.uuid4()
    request = SimpleNamespace(user=SimpleNamespace(id=user_id), query_params={"q": "  gold  "})
    profile = SimpleNamespace(id=vendor_id)
    handlers = Mock()
    handlers.list_service_packages.return_value = PageDTO(
        items=(
            ServicePackageDTO(
                id=package_id,
                vendor_id=vendor_id,
                name="Gold Package",
                description="Full reception planning and decor.",
                price=Decimal("2500000.00"),
                currency="RWF",
                package_tier="gold",
                approval_status="waiting_approval",
                rejection_reason=None,
                is_active=False,
                is_deleted=False,
                deleted_at=None,
                last_approved_at=None,
                last_vendor_public_edit_at=None,
                next_vendor_edit_allowed_at=None,
                version=0,
            ),
        ),
        total=1,
        limit=50,
        offset=0,
    )

    with patch(
        "django_app.vendors.views.packages._get_current_vendor_profile",
        return_value=(profile, None),
    ), patch(
        "django_app.vendors.views.packages.get_query_handlers",
        return_value=handlers,
    ), patch(
        "django_app.vendors.views.packages._augment_package_response",
        side_effect=lambda response: response,
    ):
        response = ServicePackageListView().get(request)

    query = handlers.list_service_packages.call_args.args[0]
    assert isinstance(query, ListServicePackagesQuery)
    assert query.vendor_id == vendor_id
    assert query.actor.user_id == user_id
    assert query.search_text == "gold"
    assert response.status_code == 200
    assert response.data["results"][0]["name"] == "Gold Package"

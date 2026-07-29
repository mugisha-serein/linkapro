from django.views import View
from rest_framework.views import APIView

from .views.profile import VendorProfileView as BaseVendorProfileView


class VendorProfileView(BaseVendorProfileView):
    """Vendor profile endpoint that keeps Django CSRF middleware enabled.

    DRF's APIView.as_view wraps API views in csrf_exempt by default. The vendor
    profile endpoint writes sensitive onboarding/profile data and can be reached
    by authenticated browser clients, so this wrapper deliberately uses Django's
    base View.as_view and preserves DRF dispatch behavior without applying the
    exemption.
    """

    @classmethod
    def as_view(cls, **initkwargs):
        view = View.as_view.__func__(cls, **initkwargs)
        view.cls = cls
        view.initkwargs = initkwargs
        view.login_required = False
        return view

    def dispatch(self, request, *args, **kwargs):
        return APIView.dispatch(self, request, *args, **kwargs)

from .url_patterns_dashboard import urlpatterns as dashboard_urls
from .url_patterns_packages2 import urlpatterns as package_urls
from .url_patterns_portfolio import urlpatterns as portfolio_urls
from .url_patterns_profile import urlpatterns as profile_urls
from .url_patterns_public2 import urlpatterns as public_urls

urlpatterns = profile_urls + portfolio_urls + package_urls + dashboard_urls + public_urls

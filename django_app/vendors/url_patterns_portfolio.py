from django.urls import path
from .views import portfolio as v
urlpatterns = [
    path("portfolio/", v.PortfolioImageView.as_view(), name="portfolio-list"),
    path("portfolio/<uuid:image_id>/", v.PortfolioImageView.as_view(), name="portfolio-detail"),
    path("portfolio/reorder/", v.PortfolioImageReorderView.as_view(), name="portfolio-reorder"),
]

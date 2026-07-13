from django.urls import path
from . import contract_views as c, views as v
urlpatterns = [
    path("portfolio/", c.PortfolioImageView.as_view(), name="portfolio-list"),
    path("portfolio/<uuid:image_id>/", c.PortfolioImageView.as_view(), name="portfolio-detail"),
    path("portfolio/reorder/", v.PortfolioImageReorderView.as_view(), name="portfolio-reorder"),
]

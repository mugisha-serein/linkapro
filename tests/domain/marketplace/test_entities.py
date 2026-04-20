import uuid
import pytest
from datetime import datetime

from domain.marketplace.entities import VendorListing, Review
from domain.shared.utils import utc_now


class TestVendorListing:
    def test_create_listing(self):
        listing = VendorListing(
            id=uuid.uuid4(),
            vendor_id=uuid.uuid4(),
            business_name="Test Photography",
            category="photography",
            description="Best photos",
            service_area="Kigali",
            cover_image_url="https://example.com/img.jpg",
        )
        assert listing.average_rating == 0.0
        assert listing.total_reviews == 0
        assert listing.is_verified is False


class TestReview:
    def test_create_valid_review(self):
        review = Review(
            id=uuid.uuid4(),
            vendor_id=uuid.uuid4(),
            author_user_id=uuid.uuid4(),
            rating=4,
            comment="Great service",
        )
        assert review.rating == 4

    def test_rating_must_be_between_1_and_5(self):
        with pytest.raises(ValueError, match="Rating must be between 1 and 5"):
            Review(
                id=uuid.uuid4(),
                vendor_id=uuid.uuid4(),
                author_user_id=uuid.uuid4(),
                rating=0,
            )
        with pytest.raises(ValueError, match="Rating must be between 1 and 5"):
            Review(
                id=uuid.uuid4(),
                vendor_id=uuid.uuid4(),
                author_user_id=uuid.uuid4(),
                rating=6,
            )
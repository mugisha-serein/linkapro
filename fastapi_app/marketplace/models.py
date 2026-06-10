from sqlalchemy import Boolean, Column, String, Float, Integer, DateTime, Text, ForeignKey, Index, Computed
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from ..database import Base
from sqlalchemy.sql import func
import uuid


class VendorListingModel(Base):
    __tablename__ = "marketplace_vendorlisting"
    __table_args__ = (
        Index("ix_marketplace_vendorlisting_external_id", "external_id"),
        Index("ix_marketplace_vendorlisting_category", "category"),
        Index("ix_marketplace_vendorlisting_service_area", "service_area"),
        Index("ix_marketplace_vendorlisting_average_rating", "average_rating"),
        Index("idx_marketplace_search_vector", "search_vector", postgresql_using="gin"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_id = Column(UUID(as_uuid=True), unique=True, nullable=False, index=True)
    external_id = Column(String(128), unique=True, nullable=True)
    business_name = Column(String(200), nullable=False)
    category = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    service_area = Column(String(200), nullable=False)
    tags = Column(Text, default="")
    cover_image_url = Column(String(500))
    average_rating = Column(Float, default=0.0)
    total_reviews = Column(Integer, default=0)
    is_verified = Column(Boolean, default=False)
    approval_status = Column(String(20), nullable=True, index=True)
    search_rank_score = Column(Float, default=0.0)
    search_vector = Column(
        TSVECTOR,
        Computed(
            "to_tsvector('simple', "
            "coalesce(business_name, '') || ' ' || "
            "coalesce(description, '') || ' ' || "
            "coalesce(category, '') || ' ' || "
            "coalesce(tags, '') || ' ' || "
            "coalesce(service_area, ''))",
            persisted=True,
        ),
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class ReviewModel(Base):
    __tablename__ = "marketplace_review"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey("marketplace_vendorlisting.vendor_id"), nullable=False, index=True)
    author_user_id = Column(UUID(as_uuid=True), nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(Text)
    is_verified_purchase = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

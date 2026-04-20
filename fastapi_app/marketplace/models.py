from sqlalchemy import Boolean, Column, String, Float, Integer, DateTime, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
import uuid

Base = declarative_base()

class VendorListingModel(Base):
    __tablename__ = "marketplace_vendorlisting"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_id = Column(UUID(as_uuid=True), unique=True, nullable=False, index=True)
    business_name = Column(String(200), nullable=False)
    category = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    service_area = Column(String(200), nullable=False)
    cover_image_url = Column(String(500))
    average_rating = Column(Float, default=0.0)
    total_reviews = Column(Integer, default=0)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index('idx_listing_search', 'business_name', 'description', 'category', postgresql_using='gin', postgresql_ops={'business_name': 'gin_trgm_ops', 'description': 'gin_trgm_ops'}),
    )

class ReviewModel(Base):
    __tablename__ = "marketplace_review"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey("marketplace_vendorlisting.vendor_id"), nullable=False, index=True)
    author_user_id = Column(UUID(as_uuid=True), nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(Text)
    is_verified_purchase = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
import uuid

from application.marketplace.queries import SearchVendorsQuery, GetVendorListingQuery, GetVendorReviewsQuery
from application.marketplace.commands import PostReviewCommand
from application.marketplace.dtos import SearchResultDTO, VendorListingDTO, ReviewDTO
from fastapi_app.dependencies import get_command_handlers, get_query_handlers
from fastapi_app.schemas import (
    SearchResponse, VendorListingResponse, ReviewResponse, PostReviewRequest
)

router = APIRouter()

@router.get("/search", response_model=SearchResponse)
async def search_vendors(
    q: Optional[str] = Query(None, description="Search query"),
    category: Optional[str] = None,
    location: Optional[str] = None,
    min_rating: Optional[float] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    handlers = Depends(get_query_handlers),
):
    query = SearchVendorsQuery(
        query=q,
        category=category,
        location=location,
        min_rating=min_rating,
        page=page,
        page_size=page_size,
    )
    result = await handlers.search_vendors(query)
    return SearchResponse(
        items=[VendorListingResponse.from_dto(item) for item in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
    )

@router.get("/vendors/{vendor_id}", response_model=VendorListingResponse)
async def get_vendor(
    vendor_id: str,
    handlers = Depends(get_query_handlers),
):
    query = GetVendorListingQuery(vendor_id=vendor_id)
    listing = await handlers.get_vendor_listing(query)
    if not listing:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return VendorListingResponse.from_dto(listing)

@router.get("/vendors/{vendor_id}/reviews", response_model=list[ReviewResponse])
async def get_vendor_reviews(
    vendor_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    handlers = Depends(get_query_handlers),
):
    query = GetVendorReviewsQuery(vendor_id=vendor_id, page=page, page_size=page_size)
    reviews, _ = await handlers.get_vendor_reviews(query)
    return [ReviewResponse.from_dto(r) for r in reviews]

@router.post("/vendors/{vendor_id}/reviews", response_model=ReviewResponse, status_code=201)
async def post_review(
    vendor_id: str,
    request: PostReviewRequest,
    handlers = Depends(get_command_handlers),
):
    # In real app, author_user_id would come from JWT token
    # For demo, we'll require it in request
    cmd = PostReviewCommand(
        vendor_id=uuid.UUID(vendor_id),
        author_user_id=uuid.UUID(request.author_user_id),
        rating=request.rating,
        comment=request.comment,
    )
    try:
        review = await handlers.post_review(cmd)
        return ReviewResponse.from_dto(review)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
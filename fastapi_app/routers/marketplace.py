from fastapi import APIRouter, Depends, HTTPException, Query
import uuid

from application.marketplace.search_service import MarketplaceSearchCriteria, MarketplaceSearchService
from application.marketplace.queries import GetVendorListingQuery, GetVendorReviewsQuery
from application.marketplace.commands import PostReviewCommand
from fastapi_app.dependencies import (
    get_command_handlers,
    get_marketplace_client_identifier,
    get_marketplace_search_params,
    get_marketplace_search_service,
    get_query_handlers,
)
from fastapi_app.schemas import (
    SearchResponse, VendorListingResponse, ReviewResponse, PostReviewRequest
)

router = APIRouter()

@router.get("/search", response_model=SearchResponse)
async def search_vendors(
    search_params: MarketplaceSearchCriteria = Depends(get_marketplace_search_params),
    client_id: str = Depends(get_marketplace_client_identifier),
    service: MarketplaceSearchService = Depends(get_marketplace_search_service),
):
    try:
        result = await service.search(search_params, client_id=client_id)
        return SearchResponse.from_dto(result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        message = str(exc).lower()
        if "rate limit" in message:
            raise HTTPException(status_code=429, detail=str(exc))
        raise

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

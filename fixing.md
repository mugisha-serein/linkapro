We are fixing LinkaPro marketplace synchronization properly, not doing demo-only work.

Goal:
Django vendor profile is the source of truth. FastAPI marketplace is the read/search projection. When a vendor is approved in Django, it must appear in FastAPI marketplace search. When rejected, suspended, draft, or incomplete, it must be removed from FastAPI marketplace. Frontend marketplace and planner vendor discovery must fetch approved vendors from FastAPI only.

Repositories:
- Backend: linkapro
- Frontend: linkapro-frontend

Backend tasks in linkapro:

1. Create a clean marketplace projection service.
   - Add a service module, for example:
     infrastructure/adapters/marketplace_projection.py
     or django_app/vendors/marketplace_projection.py
   - It must expose:
     sync_vendor_to_marketplace(vendor: VendorProfile) -> dict
     delete_vendor_from_marketplace(vendor_id: UUID | str) -> dict
     sync_or_delete_vendor_projection(vendor: VendorProfile) -> dict
   - It must call FastAPI internal endpoints:
     POST {FASTAPI_INTERNAL_URL}/internal/listings
     DELETE {FASTAPI_INTERNAL_URL}/internal/listings/{vendor_id}
   - It must send X-Internal-Secret using FASTAPI_INTERNAL_SHARED_SECRET.
   - In production, missing FASTAPI_INTERNAL_URL or FASTAPI_INTERNAL_SHARED_SECRET must raise a clear ImproperlyConfigured or RuntimeError, not silently skip.
   - In development/test, it may skip safely but must log clearly.

2. Replace duplicated sync logic.
   - Remove duplicated marketplace sync code from django_app/governance/views.py where possible.
   - Replace manual _sync_approved_vendor and _delete_vendor_listing with the new projection service.
   - Update infrastructure/repos/django_vendor_profile_repository.py to call the same projection service after saving:
       if status == approved -> sync
       else -> delete
   - Keep behavior safe: never show non-approved vendors in FastAPI.

3. Add a Django management command:
   python manage.py sync_marketplace_listings
   - It must find all VendorProfile rows where status == APPROVED.
   - For each approved vendor, call sync_vendor_to_marketplace.
   - Print summary:
       synced count
       failed count
       skipped count
   - It should continue syncing remaining vendors if one fails, then exit non-zero if any failed.
   - This command is required for backfilling existing approved vendors.

4. Improve FastAPI marketplace internals.
   - Keep /internal/listings upsert and /internal/listings/{vendor_id} delete.
   - Ensure upsert writes approval_status='approved' only for approved vendors.
   - Ensure non-approved payload deletes existing listing.
   - Ensure cache invalidates after upsert/delete.
   - Add or verify idempotency: repeated upsert for the same vendor_id updates existing row, not duplicate.

5. Improve FastAPI search behavior.
   - Keep approved-only condition:
       VendorListingModel.approval_status == "approved"
   - Change location filtering from exact equality to partial case-insensitive matching, so "Kigali" matches "Kigali, Rwanda".
   - Keep category exact match.
   - Keep q full-text search.
   - Keep page/page_size limits.

6. Add FastAPI marketplace health endpoint:
   GET /api/v1/marketplace/health
   Return:
     status
     listings_count
     approved_listings_count
   It should fail clearly if DB/table is missing.

7. Ensure schema/bootstrap is clear.
   - Do not rely on development-only startup bootstrap for production.
   - Add documentation or command instructions for applying marketplace schema before FastAPI starts.
   - If there is already a migration helper, make sure there is a production-safe way to run it.

8. Tests:
   Add or update backend tests for:
   - approving vendor syncs/upserts FastAPI listing
   - rejecting vendor removes listing
   - suspending vendor removes listing
   - approved-only FastAPI search
   - internal upsert idempotency
   - partial location search
   - sync_marketplace_listings command backfills approved vendors

Frontend tasks in linkapro-frontend:

1. Keep marketplaceService using FastAPI.
   - Do not switch public marketplace to Django.
   - Ensure query maps to q.
   - Ensure planner vendor discovery also uses FastAPI marketplace search.

2. Improve marketplace empty/error states.
   - Show "No approved vendors found" when FastAPI returns zero items.
   - Show clear unavailable message when FastAPI is down.
   - Do not show mock vendors.

3. Run:
   Backend:
     python manage.py check
     python manage.py test tests/django_app/vendors tests/django_app/governance tests/fastapi_app
   Frontend:
     npm run lint
     npm run build

Rules:
- No mocked marketplace data.
- No silent production sync skips.
- Do not show draft/rejected/suspended vendors in FastAPI search.
- Django remains source of truth.
- FastAPI remains marketplace read/search API.
- Keep existing public API routes stable.
- Provide final branch names and commit messages for backend and frontend separately.
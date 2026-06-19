Permanently fix LinkaPro vendor profile setup submission with backend-enforced onboarding, document, portfolio, package, and marketplace visibility rules.

Problem:
When a vendor fills and submits /vendor/profile/setup, the flow is still fragile. Profile save, document upload, portfolio upload, package creation, Celery/Cloudinary processing, marketplace sync, and frontend redirects can interfere with each other. This causes 400/500 errors, redirect loops, stale dashboard state, or vendors being allowed into marketplace before admin approval.

Goal:
Backend must become the single source of truth for vendor onboarding and marketplace readiness. Frontend must only call backend APIs, display backend statuses/errors, and follow backend redirect/access instructions.

Permanent rules:

1. Vendor profile save must always be independent from documents, portfolio, packages, Cloudinary, Celery, Redis, or analyzer services.
2. Vendor profile setup must stay required until backend status allows dashboard access.
3. A vendor may enter dashboard when profile status is pending_review or approved.
4. A vendor may appear in marketplace only after admin approval.
5. Vendor packages and portfolio must remain invisible from marketplace until vendor is approved and each item is approved/public-eligible.
6. Celery/Cloudinary/analyzer outages must not cause expected user actions to return 500.
7. Frontend must not invent state; it must follow backend status and human-readable errors.

Repositories:

* Backend: linkapro
* Frontend: linkapro-frontend

Backend tasks:

1. Create a backend vendor onboarding/access contract.
   Add or centralize a service/helper, for example:

   * application/vendors/onboarding_policy.py
   * domain/vendors/policies.py
   * django_app/vendors/policies.py

   It must return one clear contract for the current vendor:
   {
   "profile_status": "missing|draft|incomplete|rejected|pending_review|approved|suspended",
   "can_access_dashboard": true/false,
   "must_complete_profile": true/false,
   "can_submit_for_review": true/false,
   "marketplace_visible": true/false,
   "redirect_to": "/vendor/profile/setup" or "/vendor/dashboard" or null,
   "message": "human readable explanation"
   }

   Required behavior:

   * no profile -> must_complete_profile=true, can_access_dashboard=false, redirect_to=/vendor/profile/setup
   * draft/incomplete -> must_complete_profile=true, can_access_dashboard=false, redirect_to=/vendor/profile/setup
   * rejected -> must_complete_profile=true, can_access_dashboard=false, redirect_to=/vendor/profile/setup or /vendor/profile
   * pending_review -> can_access_dashboard=true, marketplace_visible=false, redirect_to=/vendor/dashboard
   * approved -> can_access_dashboard=true, marketplace_visible=true, redirect_to=/vendor/dashboard
   * suspended -> can_access_dashboard=false or limited, marketplace_visible=false, clear suspended message

2. Expose this contract to frontend.
   Add or update endpoint:
   GET /api/django/vendors/profile/status/
   or include the contract in GET /api/django/vendors/profile/.

   Frontend must be able to decide redirect/UI from backend contract, not duplicated hardcoded assumptions.

3. Fix POST /api/django/vendors/profile/.
   Profile save must only validate/save profile fields:

   * business_name
   * category
   * custom_category/other_category_label when category == other
   * description
   * service_area
   * contact_email
   * contact_phone if required
   * website if optional
   * any existing required profile fields

   It must not:

   * upload documents
   * upload portfolio
   * create packages
   * call Cloudinary
   * require Celery/Redis
   * sync marketplace
   * submit vendor for review automatically

   Valid profile save returns 200/201 with:

   * saved profile
   * onboarding/access contract
   * human-readable message

   Invalid profile save returns 400 with field-level errors only.

4. Enforce category "other" at backend.

   * If category == "other", custom_category/other_category_label is required.
   * If category != "other", custom category may be blank/null.
   * Return error:
     "Tell us what service you provide when choosing Other."
   * Add migration if missing.
   * Marketplace display can use custom category label, but canonical category may remain "other".

5. Fix verification document upload as background-safe.
   Endpoint:
   POST /api/django/vendors/profile/verification-documents/

   Backend must:

   * accept PDF only
   * validate extension, MIME type, %PDF magic header, file size, parseable PDF, at least 1 page, not encrypted
   * stage file safely outside DB
   * create document metadata record
   * enqueue background processing if available
   * if Celery/Redis unavailable, mark processing_deferred and return 202, not 500
   * return human-readable 400 only for actual file/user errors
   * never expose Celery/Redis/Cloudinary/analyzer details to user

   Response example:
   {
   "status": "queued",
   "processing_deferred": false,
   "document_id": "...",
   "message": "Document received. Verification will continue automatically.",
   "onboarding": { ...contract... }
   }

6. Background document processing.
   Celery task must:

   * upload staged PDF to Cloudinary as document/raw resource
   * store only Cloudinary public_id, secure_url, metadata
   * run ODCR/OCR/document analyzer if configured
   * mark document pending_review, needs_manual_review, rejected, or failed
   * retry transient failures
   * be idempotent
   * never auto-approve vendor
   * keep admin review as final authority

   If analyzer unavailable:

   * do not crash
   * mark needs_manual_review
   * continue onboarding according to submitted document rules

7. Submit-for-review endpoint.
   Endpoint:
   POST /api/django/vendors/profile/submit/

   Backend must:

   * validate profile completeness
   * require a verification document record if business rules require it
   * accept queued/processing_deferred/pending_review document as submitted, not completed
   * move vendor status to pending_review when complete
   * return updated profile and onboarding/access contract
   * never require Cloudinary upload/analyzer completion before pending_review
   * never create marketplace listing at pending_review

8. Marketplace visibility enforcement.
   Backend must enforce:

   * pending_review vendors are not visible in FastAPI marketplace
   * approved vendors are visible only after admin approval
   * rejected/suspended/draft vendors are removed/hidden from marketplace
   * packages/portfolio remain hidden publicly unless vendor is approved and item is approved/public-eligible

   Do not allow frontend to control marketplace visibility.

9. Portfolio backend enforcement.
   Apply or reuse the edited portfolio media lifecycle rules:

   * vendor dashboard may show staged/private media immediately
   * marketplace/public may show only approved vendor + approved/high-quality/uploaded media
   * images and videos supported
   * videos max 10MB
   * low-quality media not public
   * vendor delete is soft delete only
   * admin delete is hard delete only
   * analyzer failure/unavailability must not return 500
   * backend returns human-readable status/errors
   * frontend only displays backend statuses

10. Package backend enforcement.
    Apply or reuse vendor package rules:

* vendor create/edit/delete packages
* vendor delete is soft delete only
* admin hard delete only
* package status supports waiting_approval and approved, plus rejected if needed
* public/marketplace visibility requires approved vendor + approved package + active + not deleted
* package tiers Standard, Premier, Gold enforced by backend
* backend returns human-readable validation errors
* frontend only displays backend statuses/errors

11. Backend status and error response standard.
    All vendor setup related endpoints should return predictable responses:

* profile endpoint
* profile status endpoint
* submit endpoint
* document endpoint
* portfolio endpoint
* packages endpoint

Standard error style:
{
"code": "vendor_profile_incomplete",
"message": "Complete your vendor profile before continuing.",
"field_errors": {
"business_name": ["Business name is required."]
},
"redirect_to": "/vendor/profile/setup",
"onboarding": { ...contract... }
}

Avoid:

* generic "Bad request"
* unhandled 500 for expected service outages
* technical error messages shown to user

12. Frontend must follow backend contract.
    Frontend tasks:

* inspect VendorLayout, vendor profile setup page, vendor profile page, vendor dashboard, vendor packages, vendor portfolio, vendor service/hooks/types
* remove duplicated frontend-only onboarding assumptions where backend contract exists
* VendorLayout should use backend onboarding/access contract
* /vendor/profile/setup and /vendor/profile remain accessible while must_complete_profile=true
* /vendor/dashboard allowed only when backend can_access_dashboard=true
* setup page redirects to dashboard only when backend redirect_to=/vendor/dashboard or can_access_dashboard=true after submit
* no redirect because profile object merely exists
* no dashboard/setup ping-pong

13. Frontend profile setup behavior.
    Required behavior:

* Save profile -> call backend profile endpoint, display backend errors/message, stay on setup if backend says must_complete_profile
* Upload document -> call backend document endpoint, display backend message, do not block profile save
* Submit for review -> call backend submit endpoint, follow backend redirect_to
* If backend returns pending_review/can_access_dashboard, redirect once to /vendor/dashboard
* If backend returns errors, show them and stay on setup
* Do not expose Celery, Redis, Cloudinary, ODCR, analyzer names to user

14. Frontend package and portfolio behavior.

* After package/portfolio create/edit/delete, update React Query cache or invalidate immediately
* Display backend statuses:
  Waiting approval
  Approved
  Rejected
  Processing
  Failed
  Private
* Do not show staged/private media publicly
* Do not show waiting approval packages publicly
* Backend is source of truth for visibility

15. Add logout button.

* Add visible top-right logout button on /vendor/profile/setup.
* Use existing logout flow.
* Redirect to /auth/login.
* Keep UI light and consistent.

16. Tests.
    Backend tests:

* no profile returns onboarding contract redirecting to setup
* valid profile save returns onboarding contract
* invalid profile save returns field_errors
* other category requires custom category
* PDF document returns 202
* Celery unavailable returns 202 processing_deferred, not 500
* submit complete profile moves to pending_review
* pending_review can_access_dashboard=true but marketplace_visible=false
* approved marketplace_visible=true after admin approval
* rejected/suspended marketplace_visible=false
* pending_review vendor not synced to FastAPI marketplace
* approved vendor synced only after admin approval
* package/portfolio visibility respects vendor approval and item approval
* vendor soft delete keeps rows
* admin hard delete removes rows

Frontend/manual tests:

* new vendor login -> setup
* direct dashboard with missing profile -> setup
* partial profile save stays on setup
* leaving setup and logging in again returns to setup
* document deferred response does not block submit
* submit complete profile -> pending_review -> dashboard once
* pending_review login -> dashboard, not setup
* approved login -> dashboard
* no infinite redirect
* logout button works
* package/portfolio updates appear immediately from backend/cache

17. Validation commands.
    Backend:
    python manage.py makemigrations
    python manage.py check
    pytest tests/django_app/vendors tests/django_app/governance tests/fastapi_app -q

Frontend:
npm run lint for touched files
npm run build

Rules:

* Backend is source of truth.
* Frontend only calls and follows backend instructions.
* Profile save is independent from documents/packages/portfolio/background services.
* Expected background service outages return controlled 202 or safe statuses, not 500.
* Only backend controls marketplace visibility.
* Pending_review is dashboard-accessible but marketplace-hidden.
* Approved is dashboard-accessible and marketplace-visible only after admin approval.
* Vendor deletes are soft deletes.
* Admin hard deletes only.
* No raw files in DB.
* No mocked URLs or data.
* No dark UI.
* Do not weaken backend permissions.

Return:

* Root cause of current profile setup instability
* Backend onboarding contract implemented
* Files changed
* Migration names
* API response examples
* Final redirect/access rules
* Package/portfolio visibility rules
* Validation results

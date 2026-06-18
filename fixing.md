Fix LinkaPro vendor verification document 500 error, background document upload/verification fallback, ODCR/OCR verification flow, and vendor onboarding UX.

Current error:
POST https://linkapro-django.onrender.com/api/django/vendors/profile/verification-documents/ returns 500 Internal Server Error.

Problem:
The verification document endpoint must never crash because Celery, Redis, Cloudinary, or ODCR/OCR document verification is unavailable. Vendor profile save must succeed. If document background processing cannot start immediately, the app should keep a pending document/job record and continue the vendor to dashboard after profile submission. The user should see a short toast that the document will be processed automatically when the service is available again. Do not tell the user that the document is “not uploaded yet” as a failure. This should be handled as a background job state.

Goal:
Make vendor verification document upload resilient:

* PDF is accepted only after validation.
* File is staged safely.
* DB stores metadata/job status, not raw file bytes.
* Celery uploads to Cloudinary and runs ODCR/OCR verification in background.
* If Celery/broker is unavailable, endpoint still returns a controlled response, not 500.
* Vendor can continue after profile save/submission.
* Add logout button top-right on vendor setup/dashboard pages so user can return to login without manually typing URL.

Repositories:

* Backend: linkapro
* Frontend: linkapro-frontend

Backend tasks:

1. Reproduce and identify the 500 root cause.

   * Inspect Render logs or local traceback for:
     POST /api/django/vendors/profile/verification-documents/
   * Inspect:

     * django_app/vendors/views.py
     * django_app/vendors/serializers.py
     * django_app/vendors/models.py
     * tasks/document_tasks.py
     * tasks/celery.py
     * Cloudinary integration code
     * ODCR/OCR integration code if present
   * Return the exact exception causing the 500.

2. Make verification document endpoint fail-safe.

   * Endpoint must catch expected operational failures:
     Celery broker unavailable
     Redis unavailable
     Cloudinary temporarily unavailable
     ODCR/OCR service unavailable
     task dispatch failure
   * These must not return 500.
   * Endpoint should create/update a VerificationDocument record with a safe status:
     queued / pending_processing / processing_deferred
   * Return HTTP 202 Accepted with a clear response:
     {
     "status": "queued",
     "document_id": "...",
     "processing_deferred": true,
     "message": "Document received. Verification will continue automatically."
     }
   * Only return 400 for actual user/input errors:
     non-PDF
     corrupt PDF
     oversized PDF
     missing file
     missing required document type
   * Only return 403 for permission/workspace errors.
   * Never expose internal exception messages to the user.

3. PDF-only validation before staging.

   * Backend must accept PDF only.
   * Validate:
     extension .pdf
     content_type application/pdf where available
     magic header starts with %PDF
     file size <= VENDOR_VERIFICATION_DOCUMENT_MAX_SIZE_MB
     parseable PDF
     at least 1 page
     not encrypted/password-protected
   * If invalid, return field-level 400.
   * Do not call Cloudinary or ODCR/OCR for invalid files.

4. Safe file staging.

   * Do not store raw file bytes in database.
   * Save uploaded PDF temporarily to Django storage or safe media/temp path.
   * Store only:
     document_id
     vendor_id
     original_filename
     mime_type
     file_size
     local_staged_path or storage key
     upload_status
     verification_status
     cloudinary_public_id nullable
     cloudinary_secure_url nullable
     odcr_status nullable
     odcr_score nullable
     odcr_result_summary nullable
     failure_reason nullable
   * Add migrations if fields are missing.
   * Existing Cloudinary URL records must remain compatible.

5. Celery task dispatch must be resilient.

   * Try to enqueue:
     process_vendor_verification_document_task.delay(document_id)
   * If enqueue succeeds:
     upload_status = queued
     processing_deferred = false
   * If enqueue fails because broker/Celery unavailable:
     upload_status = processing_deferred
     processing_deferred = true
     log exception server-side
     return 202, not 500
   * Add a management command or periodic Celery beat task to pick up deferred documents later:
     python manage.py process_deferred_vendor_documents
     or a beat task:
     retry_deferred_vendor_document_processing
   * It should enqueue/process documents where upload_status is processing_deferred/queued and no Cloudinary URL exists.

6. Celery document processing task.

   * Task name example:
     process_vendor_verification_document_task(document_id)
   * Task must be idempotent:

     * if already uploaded and verified/pending_review, exit safely
     * if Cloudinary URL exists, do not upload duplicate
   * Steps:

     1. Re-fetch document from DB.
     2. Mark upload_status=processing.
     3. Upload staged PDF to Cloudinary as raw/document resource.
     4. Save cloudinary_public_id and cloudinary_secure_url.
     5. Run ODCR/OCR verification if configured.
     6. Store ODCR/OCR result metadata.
     7. Set verification_status:
        pending_review if ODCR passes/preflight passes
        needs_manual_review if ODCR uncertain/unavailable
        rejected if document is clearly invalid by configured rules
     8. Clean up local staged file after successful Cloudinary upload.
     9. On transient failure, retry with exponential backoff.
     10. On final failure, mark upload_status=failed and save safe failure_reason.
   * Do not auto-approve vendor solely based on ODCR/OCR.
   * ODCR/OCR is an assistive pre-check; admin review remains final.

7. ODCR/OCR integration.

   * If the intended tool is named ODCR in the project, wire that service behind an adapter:
     infrastructure/adapters/document_verification.py
   * If the actual tool is OCR, name the adapter generically:
     DocumentVerificationAdapter
   * Add env vars if needed:
     ODCR_API_URL
     ODCR_API_KEY
     ODCR_TIMEOUT_SECONDS
     ODCR_ENABLED=true/false
   * If ODCR is disabled or unavailable:
     set odcr_status = unavailable
     verification_status = needs_manual_review or pending_review
     do not crash
   * Do not claim perfect fake/forgery detection.

8. Profile save/submission behavior.

   * POST/PATCH /vendors/profile/ must save profile independently from document processing.
   * Submit-for-review should not fail only because background document processing is delayed.
   * If the profile is complete and document record is queued/deferred/pending_review, allow status pending_review according to existing business rules.
   * If current business rules require a document, accept queued/deferred document as “submitted” but not verified.
   * Vendor should be able to continue to dashboard after profile is saved/submitted.
   * Marketplace listing must still require admin approval only.

9. Frontend verification document behavior.

   * On document upload 202:
     show a short success/info toast:
     "Document received. Verification will continue automatically."
   * Do not show scary wording like:
     "Document not uploaded"
     "Celery not running"
     "Upload failed"
     unless backend returns actual failed status.
   * If backend returns processing_deferred=true:
     show:
     "Document received. We’ll process it automatically."
   * Do not block profile save because document is still processing.
   * Do not redirect vendor back to setup just because document upload is queued/deferred.
   * After successful profile submit returning pending_review, redirect to /vendor/dashboard.
   * Dashboard can show a soft pending review state, not an error.

10. Celery unavailable UX rule.

* If Celery is not running or Redis broker is unavailable:

  * backend returns 202 with processing_deferred=true
  * frontend shows toast for a few seconds
  * vendor continues to dashboard after profile submission
  * background retry command/beat later processes deferred documents
* Do not tell the user technical service names like Celery, Redis, Cloudinary, or ODCR.

11. Add logout button top-right.

* Add a visible logout button on vendor onboarding/profile setup top-right.
* Also ensure vendor dashboard top-right/topbar has logout access if not already.
* It should call existing auth logout flow.
* After logout, redirect to /auth/login.
* Do not require user to manually type login URL.
* Keep UI light and consistent.

12. Tests.
    Backend tests:

* valid PDF returns 202
* non-PDF returns 400
* corrupt PDF returns 400
* oversized PDF returns 400
* Celery enqueue success returns 202 processing_deferred=false
* Celery enqueue failure returns 202 processing_deferred=true, not 500
* Cloudinary failure inside task marks failed after retries
* ODCR/OCR unavailable does not crash task
* deferred document command/beat picks up deferred records
* profile save succeeds without completed document upload
* submit-for-review can move to pending_review with queued/deferred document if business rules require submitted document only
* marketplace still excludes pending_review vendors

Frontend tests or manual validation:

* PDF upload shows accepted toast
* deferred upload does not block redirect
* profile save/submission redirects to dashboard only after pending_review
* logout button redirects to login
* no infinite redirect between /vendor/profile/setup and /vendor/dashboard

13. Validation commands.
    Backend:
    python manage.py makemigrations --check
    python manage.py check
    pytest tests/django_app/vendors -q

Frontend:
npm run lint for touched files
npm run build

Rules:

* Never return 500 for expected background service outages.
* Never expose Celery/Redis/Cloudinary/ODCR errors to the user.
* Do not store raw document bytes in the database.
* Backend allows PDF only.
* Document processing is background-only.
* User can continue after profile save/submission.
* Do not auto-approve vendors based only on automated document checks.
* Keep pending_review vendors out of marketplace until admin approval.
* Keep light UI only.
* No mocked document URLs.

Return:

* Exact root cause of the current 500
* Files changed
* Migration names
* New response examples
* How deferred processing works
* Validation results
* Suggested backend branch/commit
* Suggested frontend branch/commit

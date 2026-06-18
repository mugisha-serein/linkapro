Fix LinkaPro vendor profile 400 error, verification document upload flow, PDF-only validation, async Cloudinary storage, document quality checks, and required “Other category” input.

Problem:
POST https://linkapro-django.onrender.com/api/django/vendors/profile/ returns 400 Bad Request when saving vendor profile. Also, vendor verification documents must not be uploaded synchronously or stored directly as raw files in the database. The database should store only Cloudinary URL/public_id/metadata after Celery background upload. Backend must only accept PDF verification documents. The document upload must go through validation/quality checks so fake/invalid documents are rejected as much as possible. Also, when vendor category is “other”, frontend must show an input asking what the vendor does, and that input must be required.

Goal:
Vendor profile creation/update must save successfully without being blocked by Cloudinary/Celery document upload. Verification document upload must be asynchronous, PDF-only, validated, and stored as Cloudinary URL/public_id metadata after upload. Category “other” must require custom category text.

Repositories:

* Backend: linkapro
* Frontend: linkapro-frontend

Backend tasks:

1. Debug and fix vendor profile 400.

   * Inspect:

     * django_app/vendors/views.py
     * django_app/vendors/serializers.py
     * django_app/vendors/models.py
     * application/vendors/commands.py
     * application/vendors/handlers.py
     * infrastructure/repos/django_vendor_profile_repository.py
   * Confirm the exact required fields for POST /api/django/vendors/profile/.
   * Ensure frontend payload matches backend serializer.
   * Ensure profile creation succeeds when valid required fields are provided.
   * Return clear field-level errors when invalid.
   * Do not let verification document upload failure prevent basic profile save.

2. Separate profile save from verification document upload.

   * Vendor profile POST/PATCH should only create/update profile fields:
     business_name
     category
     custom_category if category == "other"
     description
     service_area
     contact_email
     contact_phone
     website
     any existing required fields
   * Verification document upload should remain a separate endpoint:
     /api/django/vendors/profile/verification-documents/
   * Profile save must not require Cloudinary upload to complete.

3. Add/confirm category “other” backend support.

   * If category choices include "other", add a field:
     custom_category or other_category_label
   * Required only when category == "other".
   * If category != "other", custom_category may be blank/null.
   * Validation rule:
     category == "other" and custom_category empty -> 400 field error.
   * Marketplace projection should use custom_category label when category is "other" if appropriate for display/search, while preserving canonical category="other" if needed.
   * Add migration if model field is missing.
   * Existing vendors must not break.

4. Verification document upload must be PDF-only.

   * Backend must reject non-PDF files.
   * Validate:
     content_type == application/pdf
     file extension .pdf
     PDF magic header starts with %PDF
     file size <= configured limit
   * Add setting:
     VENDOR_VERIFICATION_DOCUMENT_MAX_SIZE_MB
     default reasonable value, for example 5MB or existing project standard.
   * Return clear 400 errors for invalid type/size/corrupt PDF.

5. Add document quality/authenticity checks.

   * Do not claim perfect fraud detection.
   * Implement practical server-side checks before upload:

     * File is parseable PDF.
     * PDF has at least 1 page.
     * PDF is not empty.
     * File is not encrypted/password protected.
     * Optional: PDF metadata/basic text extraction if available.
   * If the project already uses a PDF library, reuse it.
   * If not, add a lightweight dependency only if acceptable.
   * Store verification status:
     pending_review / processing / verified / rejected / failed
     depending on current model naming.
   * Save safe rejection/failure reason.
   * Admin should be able to review; do not auto-approve just because PDF is valid.
   * Fake-document detection should be “quality/preflight validation”, not final truth.

6. Verification document upload must be asynchronous.

   * HTTP request should:

     * validate vendor ownership/profile exists
     * validate PDF type/size/header/basic quality
     * save temporary file in safe Django storage/temp path
     * create VerificationDocument record with status=pending/processing
     * dispatch Celery task
     * return 202 Accepted with:
       {
       "status": "processing",
       "document_id": "...",
       "message": "Verification document upload is processing."
       }
   * Do not upload to Cloudinary inside the HTTP request.
   * Do not store raw file binary in database.
   * Do not pass uploaded file object directly to Celery.

7. Celery task for document upload.

   * Add or update task, for example:
     tasks/document_tasks.py
     upload_vendor_verification_document_task(document_id)
   * Task must:

     * re-fetch document record from DB
     * mark status=processing
     * upload temporary PDF to Cloudinary as raw/resource_type=raw or correct Cloudinary document mode
     * store:
       cloudinary_public_id
       cloudinary_secure_url
       original_filename
       file_size
       mime_type
     * mark status=pending_review or uploaded, depending current admin review flow
     * cleanup temporary file after successful upload
     * on failure, mark status=failed and save safe error message
     * retry transient Cloudinary/network errors with exponential backoff
     * be idempotent: if document already has Cloudinary URL and completed status, do not upload again.

8. Database model requirements.

   * Verification document model should store only metadata and URLs, not raw file bytes:
     id
     vendor/profile FK
     document_type if currently used
     original_filename
     mime_type
     file_size
     cloudinary_public_id
     cloudinary_secure_url
     upload_status
     verification_status
     failure_reason/rejection_reason
     created_at/updated_at
   * Add migrations.
   * Existing records should migrate safely.
   * Existing Cloudinary URLs should be treated as uploaded/pending_review or completed based on current rules.

9. API response/list behavior.

   * GET verification documents should include:
     id
     original_filename
     cloudinary_secure_url if uploaded
     upload_status
     verification_status
     failure_reason if failed/rejected
     created_at
   * Failed document should not break the profile page.
   * Profile save endpoint should not return 400 because a document is processing.

10. Frontend profile form fix.

* Inspect:
  vendor profile setup page
  vendor profile page
  vendor service/hooks/types
  category dropdown/options
* Fix payload sent to POST /vendors/profile/.
* Ensure required backend fields are sent.
* When category == "other":
  show input:
  “What do you do?”
  make it required
  send custom_category/other_category_label to backend
* When category changes away from “other”, clear custom category field or stop sending it.
* Show field-level validation errors from backend.

11. Frontend verification document upload.

* Only allow selecting PDF files in file input:
  accept="application/pdf,.pdf"
* Validate file extension/type/size client-side before upload.
* Still rely on backend validation as source of truth.
* On upload submit:
  show “Document upload started”
  handle 202 Accepted
  refresh/poll document list until uploaded/pending_review/failed
* Do not display fake Cloudinary URLs.
* Show processing/failed/pending review status clearly.
* Document upload failure must not erase saved profile changes.

12. Fix redirect/onboarding behavior related to profile save.

* Saving profile successfully should keep user on setup/profile page if status is still draft/incomplete.
* Submitting profile for review should redirect to dashboard only when backend returns pending_review.
* Do not redirect to dashboard just because document upload started.
* Do not create redirect loop between /vendor/dashboard and /vendor/profile/setup.

13. Tests.
    Backend tests:

* valid profile POST succeeds
* missing required field returns clear 400
* category other without custom_category returns 400
* category other with custom_category succeeds
* PDF verification document returns 202 and queues Celery task
* non-PDF file returns 400
* corrupt PDF returns 400
* oversized PDF returns 400
* Celery document upload task stores Cloudinary metadata and no raw file in DB
* Celery failure marks document failed
* profile save still succeeds even if document upload is not complete
* existing Cloudinary document records serialize correctly

Frontend validation:

* touched-file ESLint
* build passes
* category other input required
* PDF-only file picker/validation
* 202 upload response handled correctly

14. Validation commands.
    Backend:
    python manage.py makemigrations --check
    python manage.py check
    pytest tests/django_app/vendors -q

Frontend:
npm run lint for touched files
npm run build

Rules:

* Do not store raw files in database.
* Do not upload verification documents synchronously in the request.
* Do not let document upload block profile creation/update.
* Backend must accept PDF only for verification documents.
* Do not claim fake-document detection is perfect; implement practical PDF quality/preflight checks.
* Do not auto-approve vendors just because a PDF uploaded.
* Do not show mock document URLs.
* Do not weaken admin review.
* Keep Django vendor profile as source of truth.
* Keep marketplace listing only for approved vendors.
* Keep light UI only.

Return:

* Root cause of POST /vendors/profile/ 400
* Files changed
* Migration names
* New/changed API response examples
* Validation results
* Suggested backend branch and commit
* Suggested frontend branch and commit

Fix LinkaPro vendor portfolio upload so Cloudinary upload is asynchronous and production-safe.

Problem:
django_app/vendors/views.py currently uploads vendor portfolio images to Cloudinary synchronously inside the HTTP request. There is even a comment saying async upload is required, but the implementation still blocks the request. This can cause slow requests, Render timeouts, poor vendor UX, and failed uploads under load.

Goal:
Move vendor portfolio image upload into a Celery task while keeping the vendor dashboard clean and reliable.

Repository:
- Backend: linkapro
- Frontend: linkapro-frontend only if API response contract requires UI changes

Backend tasks:

1. Inspect current vendor portfolio upload flow.
   - django_app/vendors/views.py
   - vendor serializers
   - vendor models
   - application/vendors/handlers.py
   - infrastructure repos for portfolio images
   - existing Celery app/tasks setup
   - existing image/document task patterns

2. Design the async flow.
   Preferred API behavior:
   - POST /api/django/vendors/portfolio/
   - Validate auth, vendor ownership, file type, file size, and caption/order immediately.
   - Save a pending upload record or create an upload job record.
   - Dispatch Celery task to upload image to Cloudinary.
   - Return HTTP 202 Accepted with:
       {
         "status": "processing",
         "job_id": "...",
         "message": "Portfolio image upload is processing."
       }
   - Do not block HTTP request waiting for Cloudinary.

3. Add upload status tracking.
   Choose the least invasive approach:
   Option A: Add status fields to PortfolioImage model:
     upload_status: pending | processing | completed | failed
     upload_error: text nullable
     original_filename: string nullable
   Option B: Add separate VendorPortfolioUploadJob model if cleaner.
   Use migrations.

4. Celery task requirements.
   - Add task, for example:
       tasks/image_tasks.py
       upload_vendor_portfolio_image_task(...)
   - Task must:
       - Mark upload as processing.
       - Upload to Cloudinary.
       - Store public_id and secure_url.
       - Mark upload as completed.
       - On failure, mark upload as failed and save a safe error message.
       - Retry transient Cloudinary/network errors with exponential backoff.
   - Task must not trust user input blindly; re-fetch vendor/image record from DB.
   - Task must be idempotent:
       - If image is already completed, do not upload again.
       - If retried after partial success, avoid duplicate broken records when possible.

5. File handling.
   - Do not pass raw uploaded file objects directly into Celery.
   - Save upload temporarily in Django storage or a safe temporary media path first.
   - Pass only the upload record ID/path to Celery.
   - Clean up temporary file after successful Cloudinary upload.
   - On failure, keep enough metadata for retry/debug but avoid leaking sensitive local paths in API responses.

6. API response/list behavior.
   - GET /api/django/vendors/portfolio/ should return portfolio items including upload_status.
   - Completed images should include secure_url.
   - Pending/processing/failed items should be visible enough for frontend to show status.
   - Failed upload should not break portfolio list.

7. Frontend behavior if needed.
   - Vendor portfolio upload should show a toast:
       "Upload started. Your image will appear shortly."
   - Portfolio gallery should display processing state for pending images.
   - Failed items should show a clear retry/remove option only if backend supports it.
   - Do not fake completed images.
   - Do not use mock URLs.

8. Backward compatibility.
   - Existing completed portfolio images must continue working.
   - Existing records with secure_url should be treated as completed.
   - Migration should backfill upload_status='completed' for existing images that already have secure_url.

9. Validation and constraints.
   - Enforce allowed image types:
       image/jpeg
       image/png
       image/webp
   - Enforce max image size from settings, default 4MB or current project limit.
   - Return clear 400 errors for invalid files.
   - Return 202 for accepted async upload.
   - Return 403 if vendor profile is incomplete/not approved where current rules require workspace access.

10. Tests.
   Add tests for:
   - portfolio upload returns 202 and queues Celery task
   - invalid file type returns 400
   - oversized file returns 400
   - Celery task marks image completed on Cloudinary success
   - Celery task marks image failed on Cloudinary failure
   - existing completed images still serialize correctly
   - vendor cannot upload to another vendor profile
   - portfolio list includes upload_status

11. Run validation:
   - python manage.py makemigrations --check
   - python manage.py check
   - pytest tests/django_app/vendors -q
   - pytest tests -q if reasonable

Rules:
- Do not block the request with Cloudinary upload.
- Do not pass file objects directly into Celery.
- Do not break existing portfolio images.
- Do not introduce mocked portfolio URLs.
- Keep the API response honest: processing means processing, completed means uploaded.
- Keep this focused on vendor portfolio upload only.
- Do not refactor unrelated vendor dashboard logic.

Return:
- Files changed
- Migration created
- API response examples
- Validation results
- Suggested branch name
- Suggested commit message
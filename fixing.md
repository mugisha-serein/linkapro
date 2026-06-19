Fix LinkaPro vendor portfolio image/video upload 400 errors by aligning frontend and backend upload contracts, validation, status rules, and error display.

Current production error:
POST https://linkapro-django.onrender.com/api/django/vendors/portfolio/ returns 400 Bad Request from vendor dashboard portfolio upload.

Goal:
Understand and fix the current portfolio upload failure permanently. Backend remains source of truth for media rules. Frontend must only mirror backend validation and show backend human-readable errors. Valid image/video uploads should return 202 Accepted and appear immediately in the vendor portfolio without page reload.

Repositories:

* Backend: linkapro
* Frontend: linkapro-frontend

Observed current implementation:

* Backend route exists at /api/django/vendors/portfolio/.
* Frontend sends multipart FormData field "media".
* Backend accepts "media" or legacy "image".
* Backend validates MIME/type/size/header/image dimensions.
* Backend creates PortfolioImage row and queues Celery.
* Frontend currently shows generic upload failure instead of backend validation errors.

Backend tasks:

1. Inspect current backend upload flow:

   * django_app/vendors/views.py
   * django_app/vendors/serializers.py
   * django_app/vendors/models.py
   * application/vendors/handlers.py
   * infrastructure repos for portfolio images
   * tasks/image_tasks.py
   * settings for upload size limits

2. Log and reproduce the 400 cause.

   * Add temporary/debug-safe logging around PortfolioImageView.post validation failures.
   * Log:
     user_id
     vendor_id if available
     filename
     content_type
     file_size
     extension
     validation error code/message
   * Do not log file contents.
   * Remove noisy logs or keep as structured warning if useful.

3. Standardize backend 400 response shape.
   All validation failures from portfolio upload should return:
   {
   "code": "portfolio_media_invalid",
   "message": "Upload a valid portfolio image or highlight video.",
   "field_errors": {
   "media": ["Human-readable reason here."]
   }
   }

   Examples:

   * "Only JPEG, PNG, WEBP images or MP4/WEBM videos are allowed."
   * "Videos must be 10MB or smaller."
   * "Image file is too large. Maximum size is 4MB."
   * "This image is too small. Upload a clearer, higher-resolution photo."
   * "This video could not be read. Upload a valid MP4, WEBM, or MOV highlight video."
   * "Complete your vendor profile before uploading portfolio media."

4. Fix allowed MIME/type mismatch.
   Backend allowed types must remain strict:

   * image/jpeg
   * image/png
   * image/webp
   * video/mp4
   * video/webm
   * video/quicktime

   Frontend must mirror exactly these types.
   Backend must reject unsupported types with clear 400.
   If browser sends empty content_type for some valid files, backend may safely infer from extension + magic header, but must not accept unsafe files blindly.

5. Fix image validation.

   * Keep backend dimension enforcement.
   * Minimum image resolution should be centralized in settings:
     VENDOR_PORTFOLIO_MIN_IMAGE_WIDTH=800
     VENDOR_PORTFOLIO_MIN_IMAGE_HEIGHT=600
   * Use PIL safely:
     Image.open
     verify
     reopen if needed to read dimensions correctly
   * Ensure WEBP validation checks:
     header starts with RIFF and contains WEBP in the correct header bytes
   * Reject corrupt images with clear field error.
   * Reset file pointer after validation.

6. Fix video validation false negatives.

   * Keep video max size 10MB.
   * Allowed extensions:
     .mp4
     .webm
     .mov
   * Allowed MIME:
     video/mp4
     video/webm
     video/quicktime
   * Improve basic header validation:
     MP4/MOV should detect ftyp in first 64 or 128 bytes, not only 32 if needed.
     WEBM should detect EBML header.
   * If no video metadata parser exists, do not overdo complex validation in request.
   * Corrupt/unsupported video should return clear 400.
   * Valid browser-recorded MP4/WEBM/MOV under 10MB should not be falsely rejected.

7. Check vendor status rule.
   Current upload uses require_workspace=True, which may block draft/incomplete/rejected vendors.
   Decide and implement one backend rule:
   Option A:
   Portfolio upload is allowed only after vendor status is pending_review or approved.
   Then frontend must hide/disable portfolio upload during setup/draft and show backend message.
   Option B:
   Portfolio upload is allowed during setup/draft as private staged media.
   It remains invisible from marketplace until vendor approved and media approved.
   Choose the intended product rule and enforce it consistently.
   Recommended:
   Allow upload for vendors with a saved profile, including draft/pending_review/approved, but keep media private until approval.
   Block only missing profile, rejected/suspended if current business rules require blocking.
   Do not let frontend decide this rule alone.

8. Keep async/background behavior safe.

   * Valid upload should stage file, create PortfolioImage, try to enqueue Celery.
   * If Celery/Redis unavailable, return 202 with processing_deferred=true, not 500.
   * Do not wait for Cloudinary.
   * Do not store raw media bytes in DB.
   * Do not expose Celery/Cloudinary/analyzer technical errors to user.

9. Ensure successful response contract.
   Valid upload returns 202:
   {
   "status": "queued",
   "job_id": "...",
   "processing_deferred": false,
   "message": "Portfolio item received. Review will continue automatically.",
   "item": { ...PortfolioImageDTO... }
   }

10. Frontend tasks:
    Inspect:

* src/services/vendorService.ts
* src/hooks/useVendor.ts
* src/app/(vendor)/vendor/portfolio/page.tsx
* src/types/api.ts

Fix frontend validation:

* Only allow:
  image/jpeg
  image/png
  image/webp
  video/mp4
  video/webm
  video/quicktime
* Check image max size to match backend setting, default 4MB.
* Check video max size 10MB.
* Add client-side image dimension check before upload:
  minimum 800x600 or values matching backend.
* Allow videos in filter logic. Currently filtering only handles Images and All Media; add Videos filter support if UI has/needs it.

11. Frontend error handling:

* Extract backend field_errors.media[0] or message from failed upload.
* Show that exact message in the upload panel and toast.
* Do not show generic "Save failed" when backend gives a useful media error.
* Example:
  backend says "This image is too small..."
  frontend displays "This image is too small. Upload a clearer, higher-resolution photo."

12. Frontend immediate UI update:

* Current hook already inserts response.item into React Query cache.
* Keep that behavior.
* Ensure item shows using:
  local_preview_url first
  then cloudinary_secure_url
  then secure_url
* Keep polling while upload_status is staged/queued/processing/processing_deferred.
* Do not require page reload.

13. Tests:
    Backend:

* valid JPEG >= minimum returns 202
* valid PNG >= minimum returns 202
* valid WEBP >= minimum returns 202
* low-resolution image returns 400 with field_errors.media
* image > max size returns 400 with field_errors.media
* unsupported image/heic returns 400 with field_errors.media
* valid MP4 <=10MB returns 202
* valid WEBM <=10MB returns 202
* video >10MB returns 400 with field_errors.media
* corrupt video returns 400 with field_errors.media
* Celery enqueue failure returns 202 processing_deferred=true
* allowed vendor status can upload according to chosen rule
* blocked vendor status returns structured 403/400 with redirect/status contract

Frontend/manual:

* unsupported type blocked before request
* low-resolution image blocked before request
* video >10MB blocked before request
* backend field_errors.media appears in UI
* valid upload appears immediately without page refresh
* processing item polls until final status
* video filter works if present

14. Validation commands:
    Backend:
    python manage.py check
    pytest tests/django_app/vendors -q

Frontend:
npm run lint for touched files
npm run build

Rules:

* Backend is source of truth.
* Frontend mirrors backend but cannot bypass it.
* No raw media bytes in DB.
* No Cloudinary wait inside request.
* No 500 for Celery/Redis/Cloudinary unavailability.
* Valid media should return 202.
* Invalid media should return structured 400 with human-readable field_errors.media.
* Vendor dashboard should show valid staged media immediately.
* Marketplace remains approved-only.
* No mocked media URLs.
* Keep light UI only.

Return:

* Exact root cause of current 400
* Files changed
* API response examples
* Backend media rules
* Frontend validation changes
* Validation results
* Suggested backend branch/commit
* Suggested frontend branch/commit

Fix LinkaPro vendor portfolio media lifecycle with soft delete, async Cloudinary sync, local preview, image/video support, professional quality analysis, and marketplace visibility rules.

Problem:
Vendor portfolio currently needs production-grade behavior. Vendors should be able to add/edit/delete portfolio items, but delete must be soft delete only. Portfolio records must not be physically removed from the database by vendor actions. Deleted/inactive portfolio items should not show on vendor dashboard default views or marketplace/public views.

Portfolio upload should appear immediately in the vendor dashboard after the user adds it, without requiring page refresh/reload and without waiting for Cloudinary upload. The system should show a local/staged preview immediately, then sync to Cloudinary later through Celery/background jobs when available.

Portfolio must support:

* high-quality photos
* highlight videos
* video max size 10MB
* reject files beyond size limits
* reject low-quality images/videos
* professional image/media analyzer must verify media quality before public visibility

Everything important must be enforced by backend. Frontend only calls backend and displays states. Marketplace/public visibility must only happen when the vendor is approved. If vendor is not approved, portfolio/packages/profile remain invisible from marketplace.

Repositories:

* Backend: linkapro
* Frontend: linkapro-frontend

Backend architecture requirement:
Implement portfolio soft-delete and media state rules cleanly according to the existing architecture. Reuse shared/common soft-delete support if already created for packages. If no shared soft-delete exists yet, create it in the proper shared/common backend layer and apply it to portfolio media.

Backend tasks:

1. Inspect current vendor portfolio flow.

   * django_app/vendors/models.py
   * django_app/vendors/views.py
   * django_app/vendors/serializers.py
   * django_app/vendors/urls.py
   * application/vendors/commands.py
   * application/vendors/handlers.py
   * domain/vendors/entities.py
   * infrastructure/repos vendor portfolio repository
   * tasks/image_tasks.py
   * Cloudinary integration
   * marketplace projection/sync code
   * frontend vendor portfolio service/hooks/pages

2. Add or reuse shared soft-delete support.

   * Portfolio delete by vendor must not physically delete the row.
   * Use shared fields:
     is_deleted
     deleted_at
     deleted_by if available
     is_active
   * Add methods:
     soft_delete(user=None)
     restore(user=None) if needed
   * Only admin/internal code may hard delete.
   * Add migrations.
   * Existing portfolio media should migrate as not deleted and active.

3. Portfolio media model requirements.
   Update portfolio media model to support images and videos:

   * id
   * vendor/profile FK
   * media_type: image | video
   * caption
   * order
   * is_active
   * is_deleted
   * deleted_at
   * upload_status:
     staged
     queued
     processing
     uploaded
     processing_deferred
     failed
   * quality_status:
     pending_analysis
     passed
     failed
     needs_manual_review
   * visibility_status:
     private
     waiting_approval
     approved
     rejected
   * local_preview_url or staged_storage_key/path
   * cloudinary_public_id nullable
   * cloudinary_secure_url nullable
   * original_filename
   * mime_type
   * file_size
   * width nullable
   * height nullable
   * duration_seconds nullable for video
   * analyzer_score nullable
   * analyzer_summary nullable
   * failure_reason nullable
   * rejection_reason nullable
   * created_at/updated_at

   Do not store raw media bytes in database.

4. Upload endpoint behavior.
   Endpoint:
   POST /api/django/vendors/portfolio/

   It must:

   * validate authenticated vendor and ownership
   * validate vendor workspace access according to current rules
   * accept image/video file
   * enforce allowed image types:
     image/jpeg
     image/png
     image/webp
   * enforce allowed video types:
     video/mp4
     video/webm
     video/quicktime only if supported
   * enforce size limits:
     images <= configured image limit, default 4MB unless current project standard exists
     videos <= 10MB
   * run basic immediate preflight:
     file extension/type
     magic header where possible
     file size
     image dimensions readable
     video metadata readable if possible
   * save file to safe temporary/local storage
   * create portfolio record with:
     upload_status=queued or processing_deferred
     quality_status=pending_analysis
     visibility_status=private or waiting_approval
     is_active=true
     is_deleted=false
   * enqueue Celery task for Cloudinary sync and media quality analysis
   * return HTTP 202 Accepted or 201 Created with the new portfolio item immediately
   * response must include local preview/staged URL if safe to serve
   * never block request waiting for Cloudinary
   * if Celery/Redis unavailable, return success with processing_deferred=true, not 500

5. Immediate dashboard visibility.

   * Newly added portfolio item must appear immediately in vendor’s own dashboard/portfolio list.
   * It may show staged/local preview first.
   * If Cloudinary URL is not ready yet, frontend should use backend-provided safe preview URL or local object preview.
   * Backend list endpoint should include staged/queued items for the owning vendor.
   * Public/marketplace endpoints must not expose staged/private/waiting items.

6. Cloudinary sync task.
   Add/update Celery task:
   process_vendor_portfolio_media_task(media_id)

   Task must:

   * re-fetch media record from DB
   * be idempotent
   * if already uploaded and quality passed, exit safely
   * mark upload_status=processing
   * upload image/video to Cloudinary using correct resource_type:
     image for images
     video for videos
   * store:
     cloudinary_public_id
     cloudinary_secure_url
     width/height
     duration for video
     file metadata
   * clean up local staged file after successful Cloudinary upload
   * retry transient Cloudinary/network failures with exponential backoff
   * on final failure, mark upload_status=failed and store safe failure_reason
   * do not delete DB row on failure

7. Professional media analyzer.
   Add media quality analyzer adapter:
   infrastructure/adapters/media_quality_analyzer.py
   or equivalent clean architecture location.

   It should support:

   * image quality checks
   * video quality checks
   * optional external professional analyzer provider if configured

   Add env vars if external analyzer exists:
   MEDIA_ANALYZER_ENABLED=true/false
   MEDIA_ANALYZER_API_URL
   MEDIA_ANALYZER_API_KEY
   MEDIA_ANALYZER_TIMEOUT_SECONDS

   If external analyzer is unavailable:

   * do not crash
   * set quality_status=needs_manual_review
   * keep item private/not public
   * admin can review manually later

   Local fallback checks must include:
   Images:

   * minimum dimensions, for example 800x600 or current project standard
   * reject extremely low resolution
   * reject unreadable/corrupt images
   * reject empty/tiny files
   * optional blur/quality heuristic if dependencies already exist

   Videos:

   * max size 10MB
   * metadata readable
   * minimum resolution if possible
   * duration reasonable for highlight video if business rule exists
   * reject corrupt/unreadable videos

   Do not claim perfect fraud/fake detection. Treat analyzer as quality/preflight + review support.

8. Visibility and approval rules.
   Portfolio marketplace/public visibility requires:

   * vendor.status == approved
   * media.is_active == true
   * media.is_deleted == false
   * media.upload_status == uploaded
   * media.quality_status == passed or approved by admin/manual review
   * media.visibility_status == approved

   If vendor is not approved:

   * portfolio must remain invisible from marketplace/public views
   * packages must remain invisible
   * public marketplace listing must not show vendor media

   If vendor becomes approved:

   * approved portfolio media can appear publicly
   * waiting/private/failed/deleted media remains hidden

9. Admin review for portfolio media.
   Add admin/governance endpoints if missing:

   * GET /api/django/governance/vendors/portfolio/pending/
   * POST /api/django/governance/vendors/portfolio/{media_id}/approve/
   * POST /api/django/governance/vendors/portfolio/{media_id}/reject/
   * DELETE /api/django/governance/vendors/portfolio/{media_id}/hard-delete/

   Admin approval should set visibility_status=approved if upload_status and quality_status allow it.
   Rejection stores rejection_reason.
   Hard delete physically removes only for admin.
   Add audit log if governance audit already exists.

10. Vendor edit behavior.
    Vendors can edit:

* caption
* order
* maybe active/inactive
* replace media only 

If media file is replaced:

* create a new staged upload or reset upload_status/quality_status
* visibility_status returns to waiting_approval/private
* public old media must not remain visible unless explicitly designed

If only caption/order changes:

* backend decides whether approval resets; prefer no reset for order, optional reset for caption if public-facing fraud risk exists.

11. Vendor soft delete behavior.
    Endpoint:
    DELETE /api/django/vendors/portfolio/{media_id}/

Vendor delete must:

* set is_deleted=true
* set is_active=false
* set deleted_at
* remove from vendor default visible list immediately
* remove from marketplace/public immediately
* not physically delete DB row
* return success response:
  "Portfolio item removed from active listings."

Only admin hard delete can physically remove the row.

12. API list behavior.
    Vendor private list:

* shows active non-deleted portfolio items, including staged/queued/processing/uploaded/failed
* returns status fields so UI can show processing/failed/private/approved

Vendor dashboard:

* shows newly added item immediately
* hides soft-deleted items

Public/marketplace list:

* only shows public-eligible media according to visibility rules

13. Marketplace projection.
    If FastAPI marketplace projection includes portfolio media:

* sync only public-eligible portfolio media
* do not sync staged/queued/failed/deleted/private media
* invalidate marketplace cache after portfolio approval/delete if needed

If FastAPI currently only stores vendor listing:

* do not invent a large new projection unless existing public profile needs media.
* At minimum, Django public vendor profile endpoints must enforce approved-only portfolio visibility.

14. Frontend vendor portfolio UX.
    Inspect:

* src/services/vendorService.ts
* src/hooks/useVendor.ts
* vendor portfolio page/components
* vendor dashboard portfolio widgets
* marketplace/public vendor profile if it displays portfolio

Requirements:

* Allow image upload and video upload.
* File input accept:
  image/jpeg,image/png,image/webp,video/mp4,video/webm,video/quicktime
* Client-side enforce:
  video <= 10MB
  image <= configured frontend max matching backend
* Backend remains source of truth.
* On upload response:
  immediately insert item into React Query cache or invalidate/refetch
  show item without page refresh
  if local preview is available, show it
  show status badge:
  Processing
  Waiting approval
  Approved
  Failed
  Private
* Do not pretend marketplace/public visibility before approval.
* On soft delete:
  remove item from visible list immediately
  show toast:
  "Portfolio item removed from active listings."
* On failed quality analysis:
  show human-readable reason from backend if available.
* Do not show technical words like Celery, Redis, Cloudinary, or analyzer provider names to vendor.

15. Frontend marketplace/public visibility.

* Marketplace/public vendor pages should display portfolio only if backend returns it.
* Do not display local staged/private media publicly.
* If vendor is not approved, do not show vendor portfolio/packages in marketplace.

16. Human-readable errors.
    Backend must return clear errors:

* "Videos must be 10MB or smaller."
* "Only JPEG, PNG, WEBP images or MP4/WEBM videos are allowed."
* "This image is too small. Upload a clearer, higher-resolution photo."
* "This video could not be read. Upload a valid highlight video."
* "This portfolio item is waiting for review before it appears publicly."

17. Tests.
    Backend tests:

* image upload returns success/202 and creates staged item
* video upload <=10MB accepted
* video >10MB rejected with clear 400
* invalid media type rejected
* low-resolution image rejected or marked failed/needs_manual_review according to design
* Celery unavailable returns success with processing_deferred=true, not 500
* Cloudinary task uploads and stores metadata
* analyzer unavailable marks needs_manual_review, not 500
* vendor soft delete keeps DB row and hides from default list
* admin hard delete physically removes row
* public portfolio excludes non-approved vendor media
* public portfolio includes approved vendor + approved media only
* vendor cannot edit/delete another vendor’s media

Frontend/manual tests:

* upload image appears immediately without refresh
* upload video <=10MB appears immediately
* upload video >10MB blocked before request and also rejected by backend if sent
* soft delete removes item immediately
* status badges display correctly
* marketplace does not show unapproved vendor portfolio
* approved vendor public page shows approved portfolio only

18. Validation commands.
    Backend:
    python manage.py makemigrations
    python manage.py check
    pytest tests/django_app/vendors tests/django_app/governance -q

Frontend:
npm run lint for touched files
npm run build

Rules:

* Vendor delete = soft delete only.
* Admin delete = hard delete only.
* Do not store raw media bytes in database.
* Do not wait for Cloudinary upload before showing item in vendor dashboard.
* Do not expose staged/private media in marketplace.
* Backend enforces media type, size, quality, and visibility rules.
* Frontend is only a caller/display layer.
* Videos max size is 10MB.
* Low-quality media must not become public.
* Do not claim fake/fraud detection is perfect; analyzer is quality/review support.
* Approved marketplace visibility requires approved vendor and approved media.
* No mocked media URLs.
* Keep light UI only.

Return:

* Root cause of current portfolio behavior
* Files changed
* Migration names
* New API response examples
* Soft-delete design location
* Media quality/analyzer rules implemented
* Cloudinary deferred-sync behavior
* Marketplace visibility rules
* Validation results
* Suggested backend branch/commit
* Suggested frontend branch/commit

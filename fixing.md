Fix LinkaPro vendor portfolio staged media 404 by preventing backend from exposing local /media upload paths as public preview URLs.

Current error:
GET https://www.linkapro.rw/media/vendor_portfolio_uploads/.../domain.PNG 404 Not Found

Root cause:
Backend stores/returns local_preview_url using default_storage.url(temp_path), which becomes a relative /media/... URL. Frontend renders that URL on the frontend domain [www.linkapro.rw](http://www.linkapro.rw), but the frontend does not serve Django media files. Also staged upload files are private/temporary and should not be exposed as public URLs.

Goal:
Fix portfolio preview and staged media handling permanently at backend level. Backend must not return unsafe or broken local /media URLs for staged portfolio media. Frontend must show immediate local object preview before upload completes, but after reload it should show a processing placeholder until Cloudinary URL exists.

Repositories:

* Backend: linkapro
* Frontend: linkapro-frontend

Backend tasks:

1. Inspect current portfolio upload flow:

   * django_app/vendors/views.py
   * django_app/vendors/models.py
   * django_app/vendors/serializers.py
   * tasks/image_tasks.py
   * settings/media/static storage configuration
   * production settings
   * frontend portfolio rendering

2. Remove unsafe local_preview_url exposure.
   Current code likely does:
   local_preview_url = default_storage.url(temp_path)
   and saves that into PortfolioImage.local_preview_url.

   Change behavior:

   * Do not return relative /media/... URLs for staged/private files.
   * Do not expose temp_upload_path publicly.
   * For staged/queued/processing media, API should return:
     local_preview_url: null
     unless there is a secure, backend-owned, authenticated preview endpoint.
   * Keep temp_upload_path/staged_storage_key internal only.

3. Backend response contract.
   Portfolio item response should expose:

   * cloudinary_secure_url only when upload_status == uploaded and URL exists
   * secure_url only for legacy already-uploaded records
   * local_preview_url null for private staged files
   * upload_status
   * quality_status
   * visibility_status
   * failure_reason/rejection_reason if any

   Never return:

   * /media/vendor_portfolio_uploads/...
   * relative staged file URLs
   * temp_upload_path
   * internal storage keys

4. Add a safe computed display_url rule if useful.
   Backend may return:
   display_url = cloudinary_secure_url or secure_url or null

   Do not use staged local file paths as display_url.

5. Optional secure preview endpoint.
   Only implement if really needed:
   GET /api/django/vendors/portfolio/{id}/preview/

   * authenticated vendor only
   * checks ownership
   * streams staged file from storage
   * never public/marketplace
   * uses Django backend domain, not frontend domain

   If not implemented, frontend should simply show processing placeholder.

6. Make staged storage production-safe.
   If files are staged before Cloudinary upload:

   * Do not rely on Render ephemeral disk unless a persistent disk or durable object storage exists.
   * Prefer durable private storage for staging, such as S3/R2/private storage.
   * If using Render disk, document requirement and ensure Celery worker can access same storage.
   * If Celery worker cannot access the staged file, mark upload failed with human-readable reason and do not expose broken URL.

7. Celery task behavior.

   * Celery should read temp_upload_path/staged_storage_key internally.
   * Upload to Cloudinary.
   * On success:
     set cloudinary_public_id
     set cloudinary_secure_url
     set upload_status=uploaded
     clear local_preview_url if it exists
     cleanup staged file
   * On failure:
     set upload_status=failed
     set safe failure_reason
     do not return staged local file URL

8. Data cleanup migration/command.
   Add a migration or management command to clean existing broken preview URLs:

   * For PortfolioImage rows where local_preview_url starts with "/media/vendor_portfolio_uploads/" or contains "vendor_portfolio_uploads":
     set local_preview_url = null
   * Do not delete rows.
   * Do not delete Cloudinary URLs.
   * Do not touch uploaded media with cloudinary_secure_url.

9. Frontend tasks:
   Inspect:

   * src/app/(vendor)/vendor/portfolio/page.tsx
   * src/hooks/useVendor.ts
   * src/services/vendorService.ts
   * src/types/api.ts

   Fix frontend rendering:

   * Use cloudinary_secure_url or secure_url for uploaded media.
   * Do not use backend local_preview_url unless it is a valid absolute authenticated preview endpoint.
   * If no URL and upload_status is staged/queued/processing/processing_deferred:
     show a processing placeholder card, not broken img/video.
   * During the same upload session, use URL.createObjectURL(file) as temporary client-only preview before upload response.
   * Do not persist frontend object URL in backend.
   * After response.item is inserted into React Query cache, if possible attach temporary clientPreviewUrl only in frontend cache for that session.
   * On page reload, if Cloudinary URL is not ready, show processing placeholder.

10. Frontend broken image safety.

* Add onError fallback for img/video preview.
* If media fails to load, hide broken media element and show status placeholder:
  "Processing media"
  "Waiting for review"
  or failure reason from backend.
* Do not repeatedly request /media/vendor_portfolio_uploads/... from frontend domain.

11. Public/marketplace rule.

* Public marketplace/vendor pages must never render staged/private local preview URLs.
* They should only show approved uploaded Cloudinary URLs returned by backend.
* If vendor or media is not approved/public-eligible, backend should not return it publicly.

12. Tests.
    Backend tests:

* portfolio upload response for staged/queued item does not include /media/ local_preview_url
* response does not expose temp_upload_path
* uploaded item returns cloudinary_secure_url
* existing broken /media local_preview_url rows are cleaned
* public endpoint excludes staged/private media
* Celery success sets Cloudinary URL and clears local preview
* Celery failure does not expose staged URL

Frontend/manual tests:

* upload shows immediate local preview before submit
* after upload response, item appears without page refresh
* staged item with no Cloudinary URL shows processing placeholder, not broken image
* no browser request goes to https://www.linkapro.rw/media/vendor_portfolio_uploads/...
* uploaded item displays Cloudinary URL
* marketplace only displays approved Cloudinary media

13. Validation commands.
    Backend:
    python manage.py makemigrations
    python manage.py check
    pytest tests/django_app/vendors -q

Frontend:
npm run lint for touched files
npm run build

Rules:

* Backend is source of truth.
* Never expose staged private local paths as public URLs.
* Do not store raw media bytes in DB.
* Do not wait for Cloudinary before returning successful staged upload.
* Do not show broken /media URLs.
* Marketplace/public only shows approved uploaded Cloudinary media.
* Vendor dashboard may show processing placeholder for staged media.
* No mocked media URLs.
* Keep light UI only.

Return:

* Exact root cause of /media 404
* Files changed
* Migration/cleanup command name
* New API response examples
* Frontend rendering fallback behavior
* Validation results
* Suggested backend branch/commit
* Suggested frontend branch/commit

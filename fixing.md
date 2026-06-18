Fix LinkaPro vendor packages with soft delete, admin verification, package tiers, immediate frontend updates, and backend-enforced package rules.

Problem:
Vendor packages currently need stronger production rules. Vendors should be able to add/edit/delete packages, but delete must be soft delete only: mark package inactive/deleted, not remove it from the database. Deleted/inactive packages should not show on vendor dashboard active package sections or marketplace/public views. Only admin should be allowed to hard delete packages. Before packages appear publicly/marketplace, they must be verified/approved by administration to prevent fraud, fake packages, or misleading offers.

Also, packages must support different package tiers/categories:

* Standard
* Premier
* Gold

Each package tier must have backend-enforced rules that vendors cannot bypass from frontend. Backend must return human-readable errors that guide the vendor to fix mistakes. Package approval state should support at least:

* waiting_approval
* approved

After vendor creates/edits/deletes a package, the vendor dashboard/package list must update immediately without requiring page refresh/reload.

Repositories:

* Backend: linkapro
* Frontend: linkapro-frontend

Backend architecture requirement:
Implement reusable soft-delete behavior in a backend/shared or common module that respects the system folder structure and architecture. Do not hardcode soft-delete logic only inside one view if the project has shared/domain/application patterns.

Backend tasks:

1. Inspect current package flow.

   * django_app/vendors/models.py
   * django_app/vendors/views.py
   * django_app/vendors/serializers.py
   * application/vendors/commands.py
   * application/vendors/handlers.py
   * domain/vendors/entities.py
   * infrastructure/repos/vendor/package repository files
   * django_app/vendors/urls.py
   * admin/governance views if admin vendor package review already exists
   * frontend vendor package service/hooks/pages

2. Add shared soft-delete support.

   * Create a shared backend soft-delete abstraction in the correct architecture layer, for example:
     django_app/common/models.py
     or django_app/shared/models.py
     or infrastructure/shared/soft_delete.py
     depending on existing project structure.
   * Add fields like:
     is_deleted = BooleanField(default=False)
     deleted_at = DateTimeField(null=True, blank=True)
     deleted_by = ForeignKey(User, null=True, blank=True) if appropriate
   * Add reusable methods:
     soft_delete(user=None)
     restore(user=None) if needed
     hard_delete only for admin/internal use
   * Add queryset/manager helpers if suitable:
     active()
     deleted()
     with_deleted()
   * Apply this to vendor ServicePackage model.
   * Add migrations.
   * Existing packages must migrate as not deleted.

3. Vendor package delete must be soft delete.

   * Vendor DELETE /vendors/packages/{id}/ should not remove DB row.
   * It should set:
     is_deleted=true
     deleted_at=now
     is_active=false
     approval_status maybe archived/deleted if needed
   * Return a success response explaining package was removed from active listings.
   * Deleted packages should not appear in normal vendor package lists unless explicitly requested.
   * Deleted packages must never appear in public marketplace/public vendor package views.

4. Admin hard delete only.

   * Add/admin-only endpoint or service method for hard delete if needed.
   * Only users with admin/staff/governance permission may hard delete package rows.
   * Vendor users must never hard delete.
   * Add tests proving vendor delete does not physically delete and admin hard delete can.

5. Add package approval workflow.

   * Add package approval status field:
     approval_status:
     draft
     waiting_approval
     approved
     rejected
     or if keeping minimal:
     waiting_approval
     approved
     rejected
   * Vendor-created or edited packages should default to waiting_approval, not approved.
   * Any significant vendor edit to an approved package should move it back to waiting_approval unless admin-only safe fields are changed.
   * Public marketplace/package visibility requires:
     vendor.status == approved
     package.is_active == true
     package.is_deleted == false
     package.approval_status == approved
   * Vendor dashboard should show package status clearly:
     Waiting approval
     Approved
     Rejected
     Inactive
   * Do not show waiting_approval packages publicly.

6. Admin package review.

   * Add admin/governance endpoints if missing:
     GET /api/django/governance/vendors/packages/pending/
     POST /api/django/governance/vendors/packages/{package_id}/approve/
     POST /api/django/governance/vendors/packages/{package_id}/reject/
     DELETE /api/django/governance/vendors/packages/{package_id}/hard-delete/
   * Approval should set approval_status=approved.
   * Rejection should set approval_status=rejected and store rejection_reason.
   * Hard delete should physically delete only when admin requests it.
   * Return human-readable messages.
   * Audit log these actions if governance audit logging already exists.

7. Package tier/category support.

   * Add package_tier or package_category field with choices:
     standard
     premier
     gold
   * Display labels:
     Standard
     Premier
     Gold
   * Add backend validation rules for each tier.
   * Start with clear, realistic rules and centralize them in one place, for example:
     domain/vendors/package_rules.py
     or application/vendors/package_rules.py

   Example rules:
   Standard:

   * price must be greater than 0
   * name required
   * description minimum length 30
   * max included services/items if the model supports items/features
   * cannot claim premium/exclusive/VIP terms in name unless allowed
     Premier:
   * price must be greater than Standard minimum
   * description minimum length 50
   * must include stronger details/benefits if model supports features
     Gold:
   * description minimum length 80
   * price must meet Gold minimum
   * must include clear deliverables/terms
   * cannot use misleading guarantee words unless backend allows them

   If the current package model only has name, description, price, currency, is_active:
   enforce rules using those fields only.
   Do not invent complex feature tables unless needed.

8. Human-readable backend errors.

   * Validation errors must be field-level and easy to understand.
   * Example:
     {
     "package_tier": ["Choose Standard, Premier, or Gold."],
     "description": ["Gold packages must include at least 80 characters explaining deliverables and terms."],
     "price": ["Gold packages must be priced at least RWF 100,000."]
     }
   * Avoid vague errors like:
     "Invalid input"
     "Bad request"
   * Frontend should display these errors near fields or in a clear toast.

9. Package create/edit behavior.

   * Vendor can create package:
     POST /vendors/packages/
     returns created package immediately with approval_status=waiting_approval.
   * Vendor can edit package:
     PATCH /vendors/packages/{id}/
     returns updated package immediately.
     If edited package was approved, move it back to waiting_approval if public-facing fields changed.
   * Vendor can soft delete package:
     DELETE /vendors/packages/{id}/
     returns success.
   * All operations must check vendor ownership.
   * Vendor cannot edit/delete another vendor’s package.
   * Suspended/rejected/incomplete vendors should be blocked according to current workspace rules.

10. Frontend vendor package UX.

* Inspect:
  src/services/vendorService.ts
  src/hooks/useVendor.ts
  vendor packages page/components
  dashboard package summary/widgets
* After create package:
  update React Query cache immediately or invalidate/refetch so the package appears without reload.
  Show toast:
  "Package created and sent for approval."
* After edit package:
  update UI immediately.
  If approval reset:
  "Package updated and sent for approval."
* After soft delete:
  remove from visible active list immediately.
  Show toast:
  "Package removed from active listings."
* Show package status badges:
  Waiting approval
  Approved
  Rejected
  Inactive
* Do not show deleted packages in default list.
* Optionally show filter/toggle for inactive/deleted only if backend supports it.
* Do not show waiting_approval packages as public/marketplace-ready.

11. Frontend package tier/category field.

* Add required package tier selector:
  Standard
  Premier
  Gold
* Send package_tier to backend.
* Show backend validation messages clearly.
* Apply helpful frontend validation, but backend remains source of truth.
* Do not allow frontend to bypass tier rules.

12. Marketplace/public visibility.

* Ensure only approved packages appear on any public vendor profile or marketplace package sections.
* If FastAPI marketplace projection includes packages now or later:
  only sync packages with approval_status=approved and is_deleted=false and is_active=true.
* If packages are not currently projected to FastAPI, do not invent a large new marketplace package projection unless needed. At minimum, keep Django public package endpoints approved-only.

13. Tests.
    Backend tests:

* vendor creates package -> approval_status waiting_approval
* package appears in vendor own package list immediately
* package does not appear in public/marketplace until approved
* admin approves package -> appears publicly if vendor approved and package active
* vendor edits approved package public fields -> status returns to waiting_approval
* vendor soft deletes package -> DB row remains, is_deleted=true, is_active=false
* soft-deleted package hidden from vendor default list and public views
* admin hard delete physically removes row
* vendor cannot hard delete
* vendor cannot edit/delete another vendor’s package
* Standard/Premier/Gold validation rules enforced
* human-readable field errors returned

Frontend validation/manual tests:

* create package appears immediately without refresh
* edit package updates immediately
* delete removes from visible list immediately
* tier field required
* backend validation errors render clearly
* waiting approval/approved states display correctly

14. Validation commands.
    Backend:
    python manage.py makemigrations
    python manage.py check
    pytest tests/django_app/vendors tests/django_app/governance -q

Frontend:
npm run lint for touched files
npm run build

Rules:

* Do not hard delete vendor packages from vendor actions.
* Only admin may hard delete.
* Implement soft-delete in shared/common backend structure.
* Do not show inactive/deleted/waiting_approval packages publicly.
* Do not rely on frontend for package tier rules.
* Backend must enforce Standard/Premier/Gold rules.
* Backend must return human-readable errors.
* Do not introduce mocked package data.
* Do not break existing vendor dashboard.
* Keep light UI only.
* Keep current route constants and API service structure.

Return:

* Root cause of current package behavior
* Files changed
* Migration names
* New API response examples
* Package tier rules implemented
* Soft-delete design location
* Admin approval flow
* Validation results
* Suggested backend branch/commit
* Suggested frontend branch/commit

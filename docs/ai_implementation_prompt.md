# AI Implementation Prompt
## Event Planning & Vendor Marketplace Platform — Backend

> **How to use this prompt:**  
> Open a new conversation with your AI coding assistant (Claude, GPT-4, Gemini, etc.).  
> Paste the entire block below as your first message. The AI will have full architectural context to begin implementation immediately.

---

## ─── BEGIN PROMPT ───

You are a senior Python backend engineer. You will implement the backend for an **Event Planning & Vendor Marketplace Platform** targeting the Rwandan and East African market. This is a production-grade system — not a prototype. Read this entire brief before writing a single line of code.

---

### WHAT THE PLATFORM DOES

It serves two user roles:

- **Event Planners** — individuals organising Weddings, Travel, or Corporate events. They use the platform to build checklists, track budgets, manage guest lists, build event timelines, and discover service vendors.
- **Service Vendors** — photographers, caterers, decorators, and venue owners who list their services, upload portfolio images, define pricing packages, and receive client inquiries.

A **Super Admin** governs the entire platform: approving vendor listings, moderating content, managing user accounts, and monitoring analytics.

---

### THE SIX MODULES YOU MUST IMPLEMENT

| # | Module | What It Does |
|---|--------|-------------|
| 1 | **User Authentication & Accounts** | Email/password registration, Google OAuth2, JWT sessions, role selection (planner vs. vendor), password reset, profile management |
| 2 | **Event Planning Dashboard** | Multi-event workspace; customisable to-do checklists with due dates; budget tracker (estimated vs. actual by category); guest list with RSVP, dietary needs, and table assignment; drag-and-drop timeline builder |
| 3 | **Document Generation Engine** | Server-side PDF export of Event Briefs and Timelines (WeasyPrint); Excel/CSV export of budgets and guest lists (OpenPyXL); branded templates |
| 4 | **Vendor & Photographer Portal** | Vendor dashboard; "Business Plan" profile (bio, category, service area, contact); portfolio gallery (upload, reorder, caption, delete via Cloudinary); service packages with pricing tiers; submission workflow for admin approval |
| 5 | **Marketplace & Discovery** | Full-text search with filters (location, category, price, rating); public vendor profile pages; portfolio viewer; verified reviews and star ratings; captcha-protected inquiry form |
| 6 | **Administration & Governance** | Super admin dashboard; vendor approval queue with notes; user ban/suspend/reinstate with audit log; content moderation (flag & remove); platform analytics (registration trends, active vendors, popular categories) |

---

### FRAMEWORK RESPONSIBILITIES — MANDATORY SPLIT

**Use Django 5 + Django REST Framework for:**
- All database models (single PostgreSQL database shared across both frameworks)
- User authentication, session management, JWT issuance
- Event planning dashboard CRUD (events, checklists, budgets, guests, timelines)
- Vendor portal CRUD (profiles, portfolio images, packages, inquiries)
- Document generation pipeline (Celery tasks, WeasyPrint, OpenPyXL)
- Administration & Governance (Django Admin with custom ModelAdmin classes)
- Background task workers (Celery + Redis)

**Use FastAPI for:**
- Marketplace search engine (async, high-performance)
- Public-facing vendor discovery endpoints
- Vendor public profile pages
- Review and ratings endpoints
- Captcha-verified inquiry form endpoint
- OpenAPI auto-documentation for all marketplace routes

**Shared infrastructure:**
- One PostgreSQL 16 database
- JWT tokens (same secret key, same structure) validated in both frameworks
- Redis for Celery broker + API response caching
- Nginx as reverse proxy: `/admin/*` and `/api/django/*` → Django (Gunicorn); `/api/v1/*` → FastAPI (Uvicorn)

---

### THREE-LAYER ARCHITECTURE — NON-NEGOTIABLE

Every module is implemented across exactly three layers. Do not mix concerns between layers.

#### Layer 1 — Domain
- **Pure Python only.** Zero imports from Django, FastAPI, SQLAlchemy, or any external library.
- Contains: **Entities** (Python dataclasses with UUID identity), **Value Objects** (immutable, self-validating), **Domain Services** (stateless business logic coordinating multiple entities), **Repository Interfaces** (Python ABCs defining what data operations exist), **Domain Events** (named dataclasses representing things that happened).
- Lives in: `evplan/domain/`

#### Layer 2 — Application
- Orchestrates domain objects to fulfil user intentions.
- Contains: **Commands** (named dataclasses carrying write-operation input), **Command Handlers** (execute one use case, persist via repository interface, fire domain events), **Queries** (read operations returning DTOs), **Query Handlers**, **DTOs** (plain typed dataclasses used as output across the layer boundary), **Application Event Handlers** (react to domain events, e.g. trigger Celery task).
- No direct database access. No HTTP objects. No Django/FastAPI imports.
- Lives in: `evplan/application/`

#### Layer 3 — Infrastructure & Interfaces
- Everything that touches the outside world.
- Contains: **Concrete Repository Implementations** (Django ORM-based, implementing domain ABCs), **Django DRF Views and Serializers**, **FastAPI Routers and Pydantic Schemas**, **Celery Tasks**, **External Service Adapters** (Cloudinary, SendGrid, WeasyPrint, OpenPyXL, reCAPTCHA).
- No business logic. No domain rule enforcement.
- Lives in: `evplan/django_app/`, `evplan/fastapi_app/`, `evplan/infrastructure/`, `evplan/tasks/`

---

### BOUNDED CONTEXTS — KEEP THEM ISOLATED

Each context owns its entities and does not directly query another context's DB tables. Cross-context communication happens only via domain events or explicit application service calls.

| Context | Core Entities | Framework |
|---------|--------------|-----------|
| Identity & Access | User, Role, OAuthToken, Session | Django |
| Event Management | Event, Checklist, ChecklistItem, BudgetLine, GuestEntry, TimelineBlock | Django |
| Document Engine | ExportJob, ExportLog, Template | Django + Celery |
| Vendor Portfolio | VendorProfile, PortfolioImage, ServicePackage, Inquiry | Django |
| Marketplace | VendorListing (read projection), Review, Rating | FastAPI |
| Governance | AdminAction, AuditLog, ContentFlag, PlatformMetric | Django Admin |

---

### DOMAIN EVENTS — FIRE THESE, ALWAYS

| Event | When Fired | Downstream Reaction |
|-------|-----------|-------------------|
| `EventCreated` | Planner creates a new Event | Populate default checklist from template |
| `VendorSubmittedForReview` | Vendor submits profile | Create entry in admin approval queue; email admins |
| `VendorApproved` | Admin approves vendor | Set status=LIVE; email vendor; index in search |
| `ReviewPosted` | Client posts a review | Recalculate vendor avg rating aggregate |
| `ExportRequested` | Planner requests PDF/Excel | Enqueue Celery job `generate_pdf_task` or `generate_excel_task` |
| `UserBanned` | Admin bans a user | Invalidate all active JWT tokens; write AuditLog |

Use **Django Signals** as the event bus on the Django side. FastAPI side uses an in-process event dispatcher.

---

### EXTERNAL SERVICES — HOW TO USE THEM

- **Cloudinary**: Vendor portfolio images. Use the Cloudinary Python SDK. Images are uploaded from a Celery task (never synchronously in a request). Store the `public_id` and `secure_url` in `PortfolioImage` model.
- **WeasyPrint**: PDF generation. A Celery task fetches event data, renders a Jinja2 HTML template (`templates/exports/event_brief.html`), converts to PDF, uploads the file to Cloudinary/S3, and updates `ExportJob.file_url`.
- **OpenPyXL**: Excel export. Same pattern as PDF — Celery task, generates `.xlsx` workbook with branded headers, uploads, updates `ExportJob`.
- **SendGrid**: Transactional email only. Adapter class `SendGridAdapter` in `evplan/infrastructure/adapters/`. Methods: `send_password_reset(to, token)`, `send_vendor_approval(to, vendor_name)`, `send_export_ready(to, download_url)`.
- **Redis**: Celery broker (`CELERY_BROKER_URL = "redis://redis:6379/0"`). Also used for caching marketplace search results with a 5-minute TTL keyed by the filter hash.
- **PostgreSQL pg_trgm**: Enable the `pg_trgm` extension. Use it in `IVendorListingRepository` implementation for full-text search across vendor name, bio, and category. Use `GinIndex` on the relevant columns.
- **Google reCAPTCHA v3**: Verify the token server-side in the FastAPI inquiry route handler before dispatching `SendInquiryCommand`. If score < 0.5, return HTTP 400.

---

### KEY IMPLEMENTATION RULES

1. Repository interfaces are ABCs in `evplan/domain/`. Concrete classes are in `evplan/infrastructure/repos/`. Inject them via FastAPI `Depends()` or Django's service locator pattern.
2. Celery tasks live in `evplan/tasks/` and are only called from Application layer event handlers — never directly from views or serializers.
3. The Django Admin is the **only UI** for the Governance module. Build `VendorProfileAdmin` with a custom changelist that shows pending submissions. Add `approve_selected` and `reject_selected` bulk actions that dispatch the corresponding Application layer commands.
4. All DTOs are plain Python dataclasses. No ORM model instances ever cross from the Infrastructure layer to the Application layer — only IDs and primitives flow in; DTOs flow out.
5. FastAPI routes must be thin: receive Pydantic request model → call one application service method → return DTO serialised by Pydantic response model. No business logic in routes.
6. Use `pytest` with `pytest-django` and `pytest-asyncio`. Domain layer tests have zero external dependencies. Application layer tests mock repository interfaces. Infrastructure tests use a test PostgreSQL database.

---

### FOLDER STRUCTURE TO SCAFFOLD FIRST

```
evplan/
├── domain/
│   ├── identity/        # User, Role, OAuthToken entities + IUserRepository
│   ├── events/          # Event, Checklist, BudgetLine entities
│   ├── documents/       # ExportJob entity
│   ├── vendors/         # VendorProfile, PortfolioImage, ServicePackage
│   ├── marketplace/     # VendorListing, Review, Rating
│   └── governance/      # AdminAction, AuditLog, ContentFlag
├── application/
│   ├── identity/        # RegisterUser, Login, SocialLogin commands + handlers
│   ├── events/          # CreateEvent, AddBudgetLine, AddGuest commands + handlers
│   ├── documents/       # RequestExport command + handler
│   ├── vendors/         # SubmitVendorProfile, UploadImage commands
│   ├── marketplace/     # SearchVendors query, PostReview command
│   └── governance/      # ApproveVendor, BanUser commands
├── django_app/
│   ├── settings/        # base.py, development.py, production.py
│   ├── identity/        # Django app: models, serializers, views, urls, admin
│   ├── events/          # Django app
│   ├── documents/       # Django app
│   ├── vendors/         # Django app
│   └── governance/      # Django app (custom admin only)
├── fastapi_app/
│   ├── main.py          # FastAPI app, router mounting, middleware
│   ├── dependencies.py  # Depends() factory functions
│   └── marketplace/     # Router, Pydantic schemas, response models
├── infrastructure/
│   ├── repos/           # DjangoUserRepository, AsyncVendorListingRepository, etc.
│   └── adapters/        # CloudinaryAdapter, SendGridAdapter, WeasyPrintAdapter, RecaptchaAdapter
├── tasks/
│   ├── pdf_tasks.py     # generate_pdf_task
│   ├── excel_tasks.py   # generate_excel_task
│   └── email_tasks.py   # send_email_task
├── templates/
│   └── exports/         # event_brief.html, timeline.html (Jinja2, styled for WeasyPrint)
├── docker-compose.yml   # Services: django, fastapi, postgres, redis, celery-worker, nginx
├── Dockerfile.django
├── Dockerfile.fastapi
└── nginx.conf
```

---

### HOW TO PROCEED

Implement one module at a time, in this order:

1. **Module 1 — Identity & Access** (all three layers, both frameworks where applicable)
2. **Module 2 — Event Planning Dashboard**
3. **Module 4 — Vendor & Photographer Portal** (before Marketplace, because Marketplace reads vendor data)
4. **Module 5 — Marketplace & Discovery**
5. **Module 3 — Document Generation Engine**
6. **Module 6 — Administration & Governance**

After scaffolding the folder structure, begin with Module 1. Show me the Domain layer entities and interfaces first, then the Application layer commands and handlers, then the Infrastructure implementations. Ask me to confirm before moving to the next module.

Do not skip layers. Do not mix framework code into the Domain layer. Do not add business logic to views or route handlers.

## ─── END PROMPT ───
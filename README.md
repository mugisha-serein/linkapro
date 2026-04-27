<div align="center">
  <h1>Linkapro</h1>
  <h3>Event Planning & Vendor Marketplace Backend</h3>
  <p>
    <img src="https://img.shields.io/badge/Django-5.0-092E20?style=for-the-badge&logo=django&logoColor=white" alt="Django">
    <img src="https://img.shields.io/badge/FastAPI-0.110-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI">
    <img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL">
    <img src="https://img.shields.io/badge/Celery-5.4-37814A?style=for-the-badge&logo=celery&logoColor=white" alt="Celery">
    <img src="https://img.shields.io/badge/Redis-7.2-D82C20?style=for-the-badge&logo=redis&logoColor=white" alt="Redis">
    <img src="https://img.shields.io/badge/Docker-24.0-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker">
    <img src="https://img.shields.io/badge/Flutterwave-v3-orange?style=for-the-badge" alt="Flutterwave">
  </p>
</div>

---

## 📖 Table of Contents

- [1. Overview](#-overview)
- [2. System Architecture](#-system-architecture)
- [3. Domain Design (Core Logic)](#-domain-design-core-logic)
- [4. Key Features (Use Cases)](#-key-features-use-cases)
- [5. Technology Stack](#-technology-stack)
- [6. Project Structure](#-project-structure)
- [7. Getting Started](#-getting-started)
- [8. Configuration & Environment](#-configuration--environment)
- [9. Testing Strategy](#-testing-strategy)
- [10. Test Evidence](#-test-evidence)
<!-- - [11. Deployment Architecture](#-deployment-architecture) -->

---

## 📋 Overview

**Linkapro** is a domain-driven, layered backend system designed to manage event planning workflows and vendor marketplace interactions with strict separation of concerns and scalable architecture.

The system models three primary bounded actors:

- **Event Planners** — create and manage event lifecycles including budgeting, scheduling, guest coordination, and vendor selection.
- **Service Vendors** — expose structured service offerings through portfolios, pricing models, and availability management.
- **System Administrators** — enforce governance through moderation, approvals, auditability, and operational control.

Linkapro is not a monolithic application layer; it is structured around independent domains that communicate through well-defined application services and infrastructure adapters.

Core design constraints:
- Business rules are isolated within the Domain layer
- Application layer orchestrates workflows without owning rules
- Infrastructure is replaceable and framework-bound (Django, FastAPI, Celery)
- All external integrations are abstracted behind ports

---

## ✨ Key Features (Application Capabilities)

### 🔐 Identity & Access Domain
- Authentication via email/password and social OAuth2 (Google)
- Role-based access control (Event Planner / Vendor / Admin)
- Hardened JWT management with **Refresh Token Rotation**, **Family-based Blacklisting**, and **Step-up Authentication** for sensitive actions.
- 2FA (2 Factor Authentication) improves security for users
- Profile lifecycle management (update, recovery, reset)

---

### 📋 Event Management Domain
- Event lifecycle orchestration (create → plan → execute)
- Budget tracking (estimated vs actual per category)
- Task/checklist engine with due dates and status transitions
- Guest management with RSVP and metadata tracking
- Event timeline modeling and scheduling logic

---

### 📸 Vendor Management Domain
- Vendor profile aggregation (bio, category, service scope)
- Portfolio media management (upload, ordering, metadata)
- Pricing model definitions (packages and tiers)
- Vendor approval workflow via governance layer

---

### 🛒 Marketplace & Discovery (Read-Optimized Domain)
- Full-text search with multi-criteria filtering
- Public vendor exposure layer (read-only projection)
- Rating and review aggregation model
- Inquiry submission system with validation layer

---
### 💳 Payments & Financial Domain
- Secure one-time payments via **Flutterwave Standard v3**.
- Support for Mobile Money (MTN, Airtel, M-Pesa), Cards, and Bank Transfers.
- **Race condition protection** via Redis distributed locking.
- Idempotent webhook processing and strict domain-driven state machine.
- Multi-currency support (RWF, USD, EUR, KES, GHS, NGN).

---

### 📄 Document Generation Domain
- Server-side PDF generation for event reports (WeasyPrint)
- Spreadsheet exports for budgets and guest lists (OpenPyXL)
- Template-based document rendering system
- Asynchronous generation via background workers (Celery)

---

### 🛡️ Governance & Administration Domain
- Administrative control plane (Django Admin)
- Vendor approval and rejection pipeline
- User lifecycle enforcement (ban, suspend, reinstate)
- Audit logging and system traceability
- Platform-level analytics and monitoring views

---

## 🏗️ System Architecture

Linkapro is designed using a **strict layered architecture** with enforced dependency direction and clear separation of concerns. The system follows a **unidirectional flow model** to ensure testability, scalability, and framework independence.

---

### 🧠 1. Domain Layer (Core Business Rules)

The Domain Layer is completely framework-agnostic and contains the system’s business intelligence.

It includes:
- Entities
- Value Objects
- Domain Services
- Repository Interfaces
- Domain Events

**Rules:**
- No Django / FastAPI / external library dependencies
- No database access
- No HTTP or infrastructure concerns
- Defines *what the system is*, not *how it runs*

---

### ⚙️ 2. Application Layer (Use Case Orchestration)

The Application Layer coordinates business workflows without owning business rules.

It includes:
- Commands
- Queries
- Handlers / Use Cases
- DTOs (Data Transfer Objects)

**Responsibilities:**
- Executes domain logic in correct order
- Manages transaction boundaries
- Publishes domain events
- Transforms domain models into response structures

**Rules:**
- No direct database access
- No framework-specific logic
- Depends only on Domain Layer

---

### 🔌 3. Infrastructure & Interface Layer

This layer provides all external system integrations and framework implementations.

It includes:
- Django ORM repositories
- FastAPI routes/controllers
- Celery workers
- External services (Cloudinary, SendGrid, WeasyPrint)

**Responsibilities:**
- Implements repository interfaces
- Handles HTTP requests/responses
- Manages external API communication
- Executes background jobs

**Rules:**
- Can depend on Application + Domain
- Must NOT contain business rules
- Fully replaceable without affecting core logic

---

## 🔁 Dependency Rule (Strict Constraint)

```text id="dep_flow"
Infrastructure → Application → Domain

---

### 🧩 Bounded Contexts

Linkapro is decomposed into independent bounded contexts, each representing a cohesive business capability with clear ownership and isolation.

---

| Context              | Core Responsibility (Domain Scope)                         | Primary Interface Layer |
|----------------------|------------------------------------------------------------|-------------------------|
| Identity & Access    | Authentication, authorization, user lifecycle, roles       | Django                  |
| Event Management     | Event lifecycle, planning workflows, budgeting, scheduling | Django                  |
| Vendor Management    | Vendor identity, portfolios, services, availability        | Django                  |
| Marketplace          | Search, discovery, ranking, public projections             | FastAPI                 |
| Document Generation  | Report generation, exports, document rendering pipelines   | Celery Workers          |
| Payments             | Transaction lifecycle, webhooks, provider reconciliation   | Django + Flutterwave    |
| Governance           | System moderation, approvals, auditability, analytics      | Django Admin            |

---

## 🛠️ Technology Stack

The technology stack is organized by **system responsibility layers**. Each component exists to support a specific architectural concern.

---

### ⚙️ Interface Layer (Web & API Delivery)
- Django (Core application framework, admin interface, API orchestration)
- FastAPI (High-performance read API / marketplace queries)

---

### 🧠 Domain Support Layer (State & Workflow)
- PostgreSQL (Primary relational data store)
- Redis (Caching, session state, background coordination)

---

### ⚙️ Asynchronous Processing Layer
- Celery (Background job orchestration)
- Redis Broker (Task queue transport layer)

---

### 🧱 Infrastructure Layer (Deployment & Isolation)
- Docker (Containerized execution environment)
- Docker Compose (Multi-service orchestration)

---

### 🌐 External Integration Layer
- Cloudinary (Media storage and delivery)
- Google OAuth (Authentication provider integration)
- SendGrid (Transactional email delivery system)

---

### 📄 Document Processing Layer
- WeasyPrint (PDF generation engine)
- OpenPyXL (Spreadsheet generation and export engine)

---

## 📂 Project Structure

```
linkapro/
├── domain/                    # Core business logic (Entities, Value Objects, Interfaces)
│   ├── identity/
│   ├── events/
│   ├── vendors/
│   ├── marketplace/
│   ├── documents/
│   └── governance/
│
├── application/               # Use case orchestration (Commands, Handlers, DTOs)
│   ├── identity/
│   ├── events/
│   ├── vendors/
│   ├── marketplace/
│   ├── documents/
│   └── governance/
│
├── payments/                  # Payment Domain & Application logic
│   ├── domain/                # State machine, Money value objects, Policies
│   ├── application/           # Token handlers, Payment commands
│   └── infrastructure/        # Flutterwave adapters, Redis locks
│
├── django_app/                # Django configuration, Admin, and CRUD endpoints
│   ├── identity/
│   ├── events/
│   ├── vendors/
│   ├── documents/
│   ├── governance/
│   └── settings/
│
├── fastapi_app/               # High-performance Marketplace endpoints
│   ├── marketplace/
│   ├── dependencies.py
│   └── main.py
│
├── infrastructure/            # Concrete repositories and external adapters
│   ├── repos/
│   └── adapters/
│
├── tasks/                     # Celery background tasks (PDF, Excel, email)
├── templates/                 # Jinja2 templates for PDF generation
│
├── docker-compose.yml
├── Dockerfile.django
├── Dockerfile.fastapi
└── nginx.conf
```

---

## 🚀 Getting Started

This system is designed to run in a **containerized multi-service environment** (Django + FastAPI + Celery + PostgreSQL + Redis).

---

### 📦 Prerequisites

- Docker Engine (24+)
- Docker Compose v2+
- Git

---

### ⚙️ Environment Setup

```bash
git clone https://github.com/your-org/linkapro.git
cd linkapro

---

### Configure environment variables
- cp .env.example .env

---

### 🧱 System Build & Startup
- docker-compose up -d --build

---

### 🌐 Service Access Points

---

| Service      | URL                                                        |
| ------------ | ---------------------------------------------------------- |
| Django API   | [http://localhost:8000/api](http://localhost:8000/api)     |
| FastAPI Docs | [http://localhost:8001/docs](http://localhost:8001/docs)   |
| Admin Panel  | [http://localhost:8000/admin](http://localhost:8000/admin) |

---

### 🧪 Local Development Mode

---

## 1. Create virtual environment
- python -m venv env

---

## 2. Activate virtual environment
# Mac/Linux
source env/bin/activate

# Windows
env\Scripts\activate

---

## 3. Install dependencies
- pip install -r requirements/base.txt
- pip install -r requirements/fastapi.txt
- pip install -r requirements/production.txt
- pip install -r requirements/test.txt

---

### 🧪 Running Tests

The test suite is structured according to the system architecture layers. Each layer can be executed independently to ensure isolation and maintainability.

---

## ▶️ Run All Tests

```bash
pytest tests/ -v

---

## 🧠 Layered Test Execution
🧠 Domain Layer (Business Rules)
- pytest tests/domain/identity -v
- pytest tests/domain/events -v
- pytest tests/domain/vendors -v
- pytest tests/domain/marketplace -v
- pytest tests/domain/documents -v
- pytest tests/domain/governance -v

---

⚙️ Application Layer (Use Case Logic)
- pytest tests/application/identity -v
- pytest tests/application/events -v
- pytest tests/application/vendors -v
- pytest tests/application/marketplace -v
- pytest tests/application/documents -v
- pytest tests/application/governance -v

---

🔌 Infrastructure Layer (Adapters & Repositories)
- pytest tests/infrastructure/repos -v
- pytest tests/infrastructure/adapters -v

---

## 🌐 Interface Layer (Framework Boundaries)
Django Application Tests
- pytest tests/django_app/identity -v
- pytest tests/django_app/events -v
- pytest tests/django_app/vendors -v
- pytest tests/django_app/documents -v
- pytest tests/django_app/governance -v

FastAPI Application Tests
- pytest tests/fastapi_app/repos -v
- pytest tests/fastapi_app/routers -v

---

## ⚙️ Background Tasks
Tasks Tests
- pytest tests/tasks -v

---

## 📄 Test Evidence & Verification

This section provides structured proof of test execution across architectural layers. Each artifact represents validation of isolated system boundaries.

---

### 🧠 Domain Layer Validation
- Verifies business rules and invariants
- Ensures framework independence

![Domain Tests](./Evidences/domain.png)

---

### ⚙️ Application Layer Validation
- Verifies use case orchestration
- Ensures correct workflow execution across domain services

![Application Tests](./Evidences/application.png)

---

### 🔌 Infrastructure Layer Validation
- Verifies repository implementations and external adapters
- Ensures correct interaction with persistence and external services

![Infrastructure Tests](./Evidences/infrastructure.png)

---

### 🌐 Django Interface Layer Validation
- Verifies API endpoints, admin actions, and request lifecycle

![Django Tests](./Evidences/django.png)

---

### ⚡ FastAPI Interface Layer Validation
- Verifies high-performance read endpoints and query behavior

![FastAPI Tests](./Evidences/fastapi.png)

---

### ⚙️ Background Task Validation
- Verifies asynchronous execution (Celery workflows)
- Ensures reliability of long-running operations

![Task Tests](./Evidences/tasks.png)

---
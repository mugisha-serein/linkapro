<div align="center">
  <h1>🎉 Linkapro</h1>
  <h3>Event Planning & Vendor Marketplace Platform</h3>
  <p>
    <img src="https://img.shields.io/badge/Django-5.0-092E20?style=for-the-badge&logo=django&logoColor=white" alt="Django">
    <img src="https://img.shields.io/badge/FastAPI-0.110-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI">
    <img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL">
    <img src="https://img.shields.io/badge/Celery-5.4-37814A?style=for-the-badge&logo=celery&logoColor=white" alt="Celery">
    <img src="https://img.shields.io/badge/Docker-24.0-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker">
  </p>
</div>

---

## 📖 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [Technology Stack](#-technology-stack)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
- [Environment Variables](#-environment-variables)
- [Running Tests](#-running-tests)
- [Test Evidence](#-test-evidence)

---

## 📋 Overview

**Linkapro** is a production‑grade backend system that connects **Event Planners** with **Service Vendors**.  
Whether you're planning a wedding, corporate gathering, or travel experience, Linkapro streamlines the entire workflow:

- **Planners** build checklists, track budgets, manage guest lists, and discover trusted vendors.
- **Vendors** showcase their portfolios, define pricing packages, and receive client inquiries.
- **Administrators** govern the platform with approval workflows, content moderation, and real‑time analytics.

---

## ✨ Key Features

<table>
  <tr>
    <td width="50%">
      <h4>🔐 Identity & Access</h4>
      <ul>
        <li>Email/Password registration with role selection (Planner / Vendor)</li>
        <li>Google OAuth2 integration</li>
        <li>JWT‑based sessions with refresh tokens</li>
        <li>Profile management & password reset</li>
      </ul>
    </td>
    <td width="50%">
      <h4>📋 Event Planning Dashboard</h4>
      <ul>
        <li>Multi‑event workspace</li>
        <li>Customizable checklists with due dates</li>
        <li>Budget tracker (estimated vs. actual by category)</li>
        <li>Guest list with RSVP, dietary needs & table assignments</li>
        <li>Drag‑and‑drop timeline builder</li>
      </ul>
    </td>
  </tr>
  <tr>
    <td>
      <h4>📸 Vendor & Photographer Portal</h4>
      <ul>
        <li>Business profile with bio, category, service area</li>
        <li>Portfolio gallery (Cloudinary upload, reorder, captions)</li>
        <li>Service packages with pricing tiers</li>
        <li>Admin approval workflow</li>
      </ul>
    </td>
    <td>
      <h4>🛒 Marketplace & Discovery</h4>
      <ul>
        <li>Full‑text search with filters (location, category, price, rating)</li>
        <li>Public vendor profile pages</li>
        <li>Verified reviews and star ratings</li>
        <li>Captcha‑protected inquiry form</li>
      </ul>
    </td>
  </tr>
  <tr>
    <td>
      <h4>📄 Document Generation Engine</h4>
      <ul>
        <li>Server‑side PDF export of Event Briefs & Timelines (WeasyPrint)</li>
        <li>Excel/CSV export of budgets and guest lists (OpenPyXL)</li>
        <li>Branded templates</li>
        <li>Background processing via Celery</li>
      </ul>
    </td>
    <td>
      <h4>🛡️ Administration & Governance</h4>
      <ul>
        <li>Super admin dashboard (Django Admin)</li>
        <li>Vendor approval queue with notes</li>
        <li>User ban/suspend/reinstate with audit log</li>
        <li>Content flagging & moderation</li>
        <li>Platform analytics dashboard</li>
      </ul>
    </td>
  </tr>
</table>

---

## 🏗️ System Architecture

Linkapro strictly adheres to a **Three‑Layer Architecture** to keep the codebase maintainable, testable, and framework‑agnostic.

<div style="background-color: #f6f8fa; padding: 15px; border-radius: 8px;">
  <h4 style="margin-top: 0;">🧠 1. Domain Layer</h4>
  <p>Pure Python code containing <strong>Entities</strong>, <strong>Value Objects</strong>, <strong>Repository Interfaces</strong>, and <strong>Domain Events</strong>. No external dependencies.</p>

  <h4>⚙️ 2. Application Layer</h4>
  <p>Orchestrates use cases via <strong>Commands</strong>, <strong>Queries</strong>, and <strong>Handlers</strong>. Returns <strong>DTOs</strong> and fires domain events.</p>

  <h4>🔌 3. Infrastructure & Interfaces</h4>
  <p>Contains concrete repository implementations (Django ORM), FastAPI routers, Celery tasks, and external adapters (Cloudinary, SendGrid, WeasyPrint).</p>
</div>

### Bounded Contexts

| Context               | Framework      | Core Responsibilities                              |
|-----------------------|----------------|----------------------------------------------------|
| Identity & Access     | Django + DRF   | Authentication, user profiles, roles               |
| Event Management      | Django + DRF   | Events, checklists, budgets, guests, timelines     |
| Vendor Portfolio      | Django + DRF   | Vendor profiles, images, packages, inquiries       |
| Marketplace           | **FastAPI**    | High‑performance search, reviews, public profiles  |
| Document Engine       | Django + Celery| PDF/Excel generation, export jobs                  |
| Governance            | Django Admin   | Approval workflows, audit logs, metrics            |

---

## 🛠️ Technology Stack

<div style="display: flex; flex-wrap: wrap; gap: 10px;">
  <span style="background: #092E20; color: white; padding: 6px 12px; border-radius: 20px;">Django 5</span>
  <span style="background: #009688; color: white; padding: 6px 12px; border-radius: 20px;">FastAPI</span>
  <span style="background: #4169E1; color: white; padding: 6px 12px; border-radius: 20px;">PostgreSQL 16</span>
  <span style="background: #37814A; color: white; padding: 6px 12px; border-radius: 20px;">Celery</span>
  <span style="background: #D82C20; color: white; padding: 6px 12px; border-radius: 20px;">Redis</span>
  <span style="background: #2496ED; color: white; padding: 6px 12px; border-radius: 20px;">Docker</span>
  <span style="background: #FF6C37; color: white; padding: 6px 12px; border-radius: 20px;">Cloudinary</span>
  <span style="background: #ff6c372a; color: white; padding: 6px 12px; border-radius: 20px;">OAuth Google</span>
  <span style="background: #00B2A9; color: white; padding: 6px 12px; border-radius: 20px;">SendGrid</span>
  <span style="background: #4B8BBE; color: white; padding: 6px 12px; border-radius: 20px;">WeasyPrint</span>
  <span style="background: #1F6F3B; color: white; padding: 6px 12px; border-radius: 20px;">OpenPyXL</span>
</div>

---

## 📂 Project Structure
## Project Structure

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

### Prerequisites

- Docker & Docker Compose
- Python 3.12 for local development

### Quick Start with Docker

1. **Clone the repository**
   ```bash
   - git clone https://github.com/your-org/linkapro.git
   - cd linkapro

2. Configure Environment
   - pythoh -m venv env

   - source env/bin/activate (Mac/Linux)
   - env\Scripts\activate (Windows)

3. **Install Dependencies**
   - pip install -r requirements/base.txt
   - pip install -r requirements/fastapi.txt
   - pip install -r requirements/production.txt
   - pip install -r requirements/test.txt

4. Copy environment variables
   - cp .env.example .env
   # Edit .env with your secret keys and service credentials

5. Build and run the services
   - docker-compose up -d --build

7. Access the applications
   - Django: http://localhost:8000/api/django/
   - FastAPI Swagger: http://localhost:8001/docs
   - Django Admin: http://localhost:8000/admin/

---

## 🧪 Running Tests
# Or locally (with virtual environment)
   - pytest tests/ -v

To run only a specific module:
    # Domain layer tests
        - pytest tests/domain/identity -v
        - pytest tests/domain/events -v
        - pytest tests/domain/vendors -v
        - pytest tests/domain/marketplace -v
        - pytest tests/domain/documents -v
        - pytest tests/domain/governance -v

    # Application layer tests
        - pytest tests/application/identity -v
        - pytest tests/application/events -v
        - pytest tests/application/vendors -v
        - pytest tests/application/marketplace -v
        - pytest tests/application/documents -v
        - pytest tests/application/governance -v

    # Infrastructure Layer tests
        - pytest tests/infrastructure/repos -v
        - pytest tests/infrastructure/adapters -v

    # Django app tests
        - pytest tests/django_app/identity -v
        - pytest tests/django_app/events -v
        - pytest tests/django_app/vendors -v
        - pytest tests/django_app/documents -v
        - pytest tests/django_app/governance -v

    # FastAPI app tests
        - pytest tests/fastapi_app/repos -v
        - pytest test/fastapi_app/routers -v

    # Tasks tests
        - pytest tests/tasks -v

---

## 📄 Test Evidence

## Domain Layer Tests
<div align="center"> <img src="./Evidences/domain.png" alt="Test Execution Results" style="max-width: 100%; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);"> </div>

## Application Layer Tests
<div align="center"> <img src="./Evidences/application.png" alt="Test Execution Results" style="max-width: 100%; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);"> </div>

## Infrastructure Layer Tests
<div align="center"> <img src="./Evidences/infrastructure.png" alt="Test Execution Results" style="max-width: 100%; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);"> </div>

## Django App Tests
<div align="center"> <img src="./Evidences/django.png" alt="Test Execution Results" style="max-width: 100%; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);"> </div>

## FastAPI App Tests
<div align="center"> <img src="./Evidences/fastapi.png" alt="Test Execution Results" style="max-width: 100%; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);"> </div>

## Tasks Tests
<div align="center"> <img src="./Evidences/tasks.png" alt="Test Execution Results" style="max-width: 100%; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);"> </div>

---

## License
<div align="center"> <p> <a href="#"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a> </p> </div>
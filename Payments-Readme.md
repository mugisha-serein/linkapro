<div align="center">
💳 Linkapro Payments
Secure, Hardened Payment Processing for Event & Vendor Ecosystems
<p> <img src="https://img.shields.io/badge/Flutterwave-v3-orange?style=for-the-badge" /> <img src="https://img.shields.io/badge/Redis-Distributed_Locks-red?style=for-the-badge&logo=redis" /> <img src="https://img.shields.io/badge/Celery-Reliable_Tasks-green?style=for-the-badge&logo=celery" /> <img src="https://img.shields.io/badge/Architecture-Clean_+_Layered-blue?style=for-the-badge" /> <img src="https://img.shields.io/badge/Security-Audit_Grade-black?style=for-the-badge" /> </p> </div>
📖 Overview

Linkapro Payments is a production-grade, audit-ready payment module engineered for event planning and vendor marketplaces across Rwanda and East Africa.

It supports secure one-time payments via Flutterwave Standard v3, with full protection against:

Race conditions
Double processing
Data inconsistencies
Fraud scenarios
Supported Payment Methods
Card payments (hosted)
Mobile Money (MTN MoMo, Airtel, M-Pesa)
Bank transfer
Supported Currencies

RWF · USD · EUR · KES · GHS · NGN

🎯 Design Goals
Deterministic behavior under concurrency
Strict domain-driven boundaries
Zero trust on external systems
Full auditability (7-year traceability)
Idempotent operations everywhere
🏗️ System Architecture

The system enforces a strict layered architecture with unidirectional flow:
Interface → Application → Domain
                    ↓
             Infrastructure (via ports)

Layer Responsibilities
| Layer              | Responsibility                            | Constraints                   |
| ------------------ | ----------------------------------------- | ----------------------------- |
| **Domain**         | Business rules, invariants, state machine | No DB, no HTTP, no frameworks |
| **Application**    | Orchestration, workflows                  | Uses ports only               |
| **Infrastructure** | External systems (DB, APIs, Redis)        | Implements interfaces         |
| **Interface**      | Django views (HTTP boundary)              | Delegates only                |

Why This Matters
Domain is pure and fully testable
Application is framework-agnostic
Infrastructure is replaceable without impact
System enforces zero cross-layer leakage


🧠 Domain Model
Money (Value Object)

All monetary values use integer minor units to eliminate floating-point errors.

# RWF 10,000
Money(minor_units=10000, currency="RWF")

# USD 10.99
Money.from_decimal("10.99", "USD") → 1099


Payment (Entity)
| Field              | Type         | Description                         |
| ------------------ | ------------ | ----------------------------------- |
| id                 | UUID         | Unique identifier                   |
| user_id            | UUID         | Payment owner                       |
| amount             | Money        | Minor-unit value                    |
| method             | Enum         | card / mobile_money / bank_transfer |
| status             | Enum         | Lifecycle state                     |
| reference          | String       | Internal unique reference           |
| idempotency_key    | String       | Prevents duplicate requests         |
| provider_reference | String       | External transaction ID             |
| expires_at         | UTC datetime | Default: +30 minutes                |
| environment        | Enum         | test / live                         |


State Machine

INITIATED → PENDING → SUCCESS → REFUND_REQUESTED → REFUNDED
     ↓         ↓          ↓
  CANCELLED  FAILED    (rollback possible)
     ↓         ↓
  EXPIRED   EXPIRED

Key property:
No illegal transitions are possible. All state changes pass through policy validation.


Payment Policy (Core Engine)
PaymentPolicy.apply(payment, action, context, now) → PolicyResult

Guarantees
Pure function (no side effects)
Deterministic decision-making
Centralized rule enforcement
Validation Example: CONFIRM_SUCCESS
Status must be PENDING
Provider verification must be valid
Provider reference must match
Amount & currency must match exactly
Payment must not be expired
Environment must match

Fraud detection is embedded directly in decision logic.


🔄 Payment Lifecycle
1. Initiation (Client → API)
POST /api/django/payments/initiate/

Input

{
  "amount": "10000.00",
  "currency": "RWF",
  "method": "mobile_money",
  "idempotency_key": "uuid",
  "customer_email": "client@example.com",
  "environment": "live"
}

Output

{
  "reference": "pay_xxx",
  "payment_link": "https://flutterwave.com/pay/...",
  "expires_at": "ISO8601"
}

2. Webhook Processing (Critical Path)
POST /api/django/payments/webhooks/flutterwave/


Execution Pipeline (Strict Order)
| Step | Action                           | Failure Strategy           |
| ---- | -------------------------------- | -------------------------- |
| 1    | Verify signature (constant-time) | 401                        |
| 2    | Check idempotency (event_id)     | Return 200                 |
| 3    | Store event (PROCESSING)         | —                          |
| 4    | Acquire Redis lock               | Retry via Celery           |
| 5    | Verify with provider API         | Retry (30s / 2m / 10m)     |
| 6    | Resolve payment                  | Mark UNKNOWN               |
| 7    | Apply domain policy              | Fraud signal or transition |
| 8    | Release lock + finalize          | —                          |


Critical Rule

Webhook always returns HTTP 200
Failures are handled internally via retry mechanisms.


3. Status Polling
GET /api/django/payments/status/{reference}/

4. Expiration (Background Job)
Scheduled via Celery Beat
Applies domain policy to stale payments
Ensures no dangling transactions


🔒 Security Model
| Category              | Strategy                        |
| --------------------- | ------------------------------- |
| Card Safety           | Hosted payment page only        |
| Webhook Auth          | Constant-time hash verification |
| Idempotency           | event_id + idempotency_key      |
| Concurrency           | Redis distributed locking       |
| Trust Model           | Webhook data is never trusted   |
| Validation            | Exact integer comparison        |
| Audit                 | Append-only logs (7 years)      |
| Environment Isolation | Strict test/live separation     |
| Transport             | HTTPS + HSTS                    |


📡 API Surface
| Method | Endpoint                          | Purpose        |
| ------ | --------------------------------- | -------------- |
| POST   | `/payments/initiate/`             | Create payment |
| GET    | `/payments/status/{ref}/`         | Check status   |
| POST   | `/payments/webhooks/flutterwave/` | Receive events |


🔧 Operations & Monitoring
Audit Logs
Append-only
Fraud signals flagged explicitly
No mutation allowed
Webhook Monitoring

Track:

REJECTED_*
VERIFY_FAILED_RETRY
Background Jobs
Expiry enforcement
Retry pipelines
Redis
High availability required
TTL prevents deadlocks


⚠️ Non-Negotiable Guarantees
No double charge possible
No silent failure
No trust in external input
No business logic outside domain
No state mutation without policy